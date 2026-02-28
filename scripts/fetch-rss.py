#!/usr/bin/env python3
"""
AI Signal — Feed Fetcher
Fetches from 12 sources (RSS + HTML scrape), merges with existing data,
keeps a rolling 30-day window. Outputs veille-data.json.
"""

import json, os, re, sys, time
# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
SOURCES = [
    # ── Tier 1: Major Labs ──
    {"id": "anthropic",   "name": "Anthropic",       "color": "#d4a27a", "type": "scrape", "url": "https://www.anthropic.com/news"},
    {"id": "openai",      "name": "OpenAI",           "color": "#10b981", "type": "rss",    "url": "https://openai.com/blog/rss.xml"},
    {"id": "gemini",      "name": "Google Gemini",    "color": "#4285f4", "type": "rss",    "url": "https://blog.google/products/gemini/rss/"},
    {"id": "google",      "name": "Google AI",        "color": "#34a853", "type": "rss",    "url": "https://blog.google/technology/ai/rss/"},
    {"id": "deepmind",    "name": "DeepMind",         "color": "#5c9bff", "type": "rss",    "url": "https://blog.research.google/atom.xml"},
    {"id": "meta",        "name": "Meta AI",          "color": "#0064e0", "type": "rss",    "url": "https://engineering.fb.com/category/ml-applications/feed/"},
    {"id": "xai",         "name": "xAI",              "color": "#e5e5e5", "type": "scrape", "url": "https://x.ai/news"},
    {"id": "mistral",     "name": "Mistral",          "color": "#ff7043", "type": "scrape", "url": "https://mistral.ai/fr/news"},
    # ── Tier 2: Models & Infra ──
    {"id": "huggingface", "name": "HuggingFace",      "color": "#ff9500", "type": "rss",    "url": "https://huggingface.co/blog/feed.xml"},
    {"id": "nvidia",      "name": "NVIDIA",           "color": "#76b900", "type": "rss",    "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/"},
    {"id": "microsoft",   "name": "Microsoft AI",     "color": "#00a4ef", "type": "rss",    "url": "https://blogs.microsoft.com/ai/feed/"},
    {"id": "aws",         "name": "AWS ML",           "color": "#ff9900", "type": "rss",    "url": "https://aws.amazon.com/blogs/machine-learning/feed/"},
    {"id": "databricks",  "name": "Databricks",       "color": "#ff3621", "type": "rss",    "url": "https://www.databricks.com/feed"},
    {"id": "replicate",   "name": "Replicate",        "color": "#6366f1", "type": "rss",    "url": "https://replicate.com/blog/rss"},
    # ── Tier 3: Tools & Research ──
    {"id": "langchain",   "name": "LangChain",        "color": "#1c3a5e", "type": "rss",    "url": "https://blog.langchain.com/rss/"},
    {"id": "elevenlabs",  "name": "ElevenLabs",       "color": "#f5c518", "type": "scrape", "url": "https://elevenlabs.io/blog"},
    {"id": "cohere",      "name": "Cohere",           "color": "#39d353", "type": "scrape", "url": "https://cohere.com/blog"},
    {"id": "gradient",    "name": "The Gradient",     "color": "#a855f7", "type": "rss",    "url": "https://thegradient.pub/rss/"},
]

# Category detection keywords
CATEGORIES = {
    "model":    ["model", "gpt", "claude", "gemini", "llm", "release", "launch", "version", "update", "benchmark", "mistral", "llama", "phi", "qwen", "weights", "open source"],
    "research": ["paper", "research", "study", "findings", "dataset", "training", "architecture", "attention", "transformer", "experiment", "arxiv", "preprint", "evaluation"],
    "safety":   ["safety", "alignment", "constitutional", "responsible", "risk", "bias", "red team", "policy", "harm", "trust", "interpretability", "fairness"],
    "product":  ["api", "product", "pricing", "enterprise", "partnership", "integration", "deploy", "platform", "cloud", "service", "app", "tool", "plugin", "feature"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,application/rss+xml,application/atom+xml,text/html,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_PER_SOURCE = 20
ROLLING_DAYS = 30
MAX_TOTAL = 400
TIMEOUT = 15

# ---------------------------------------------------------------------------
# Grok AI Analysis (style Watts Else — FR)
# ---------------------------------------------------------------------------
GROK_API_KEY   = os.environ.get("GROK_API_KEY", "")
GROK_MODEL     = "grok-3-mini"
GROK_URL       = "https://api.x.ai/v1/chat/completions"
MAX_TO_ANALYZE = 100  # per run (bumped for full re-analysis)
GROK_DELAY     = 0.8  # seconds between calls

ANALYSIS_PROMPT = """Tu es analyste IA pour un feed de veille tech (iamsupersocks.com).
Analyse cet article sur l'industrie de l'IA. Sois précis, critique, sans remplissage.

Titre : {title}
Source : {source}
Catégorie : {category}
Extrait : {excerpt}

Réponds UNIQUEMENT avec du JSON valide (sans balises markdown) :
{{
  "signal": "L'information clé en une phrase percutante. Pas de tournure générique.",
  "summary": "2-3 phrases : ce qui s'est passé, ce qui a été annoncé, ce qui a changé.",
  "context": "2-3 phrases : contexte plus large, pourquoi c'est important maintenant, dans quelle dynamique de marché ça s'inscrit.",
  "critique": "2-3 phrases : ce qui est notable, ce qui manque, ce que ça révèle sur la direction de l'industrie. Analytique, pas descriptif.",
  "themes": ["Thème1", "Thème2", "Thème3"]
}}

Règles :
- Ne jamais commencer par 'Cet article', 'Cette annonce', 'Ce post'
- Technique quand c'est pertinent
- La critique doit apporter de la valeur au-delà du résumé — challenger, contextualiser, signaler les angles morts"""

def call_grok(title, excerpt, source_name, category):
    if not GROK_API_KEY:
        return None
    prompt = ANALYSIS_PROMPT.format(
        title=title[:300], excerpt=excerpt[:500],
        source=source_name, category=category
    )
    body = json.dumps({
        "model": GROK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 500,
        "temperature": 0.4,
    }).encode("utf-8")
    req = Request(GROK_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROK_API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    }, method="POST")
    try:
        with urlopen(req, timeout=25) as r:
            resp = json.loads(r.read().decode("utf-8"))
        text = resp["choices"][0]["message"]["content"]
        result = json.loads(text)
        if isinstance(result.get("signal"), str) and isinstance(result.get("summary"), str):
            return {
                "signal":  result.get("signal",  "")[:300],
                "summary": result.get("summary", "")[:600],
                "context": result.get("context", "")[:600],
                "critique":result.get("critique","")[:600],
                "themes":  [str(t)[:60] for t in result.get("themes", [])[:6]],
                "model":   GROK_MODEL,
            }
    except HTTPError as e:
        print(f"HTTP {e.code}", end=" ")
    except Exception as e:
        print(f"ERR({str(e)[:40]})", end=" ")
    return None

# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------
def fetch_url(url, timeout=TIMEOUT):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as r:
        charset = "utf-8"
        ct = r.headers.get("Content-Type", "")
        m = re.search(r"charset=([^\s;]+)", ct)
        if m:
            charset = m.group(1)
        return r.read().decode(charset, errors="replace")

def strip_tags(html):
    class S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, d):
            self.parts.append(d)
        def get(self):
            return re.sub(r"\s+", " ", " ".join(self.parts)).strip()
    s = S(); s.feed(str(html)); return s.get()

def parse_date_str(raw):
    if not raw: return ""
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            s = raw[:len(fmt.replace("%z",""))]
            dt = datetime.strptime(raw, fmt) if "%z" in fmt else datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except: pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc).isoformat()
    except: pass
    return ""

def detect_category(title, excerpt):
    text = (title + " " + excerpt).lower()
    for cat, kws in CATEGORIES.items():
        if any(kw in text for kw in kws):
            return cat
    return "other"

def clean_text(raw, maxlen=0):
    """Strip HTML tags, decode entities, remove residual fragments."""
    text = strip_tags(unescape(str(raw or "")))
    # Remove any remaining HTML-like fragments (e.g. entity-decoded <img src=...>)
    text = re.sub(r"<[^>]{0,600}>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:maxlen] if maxlen else text

def make_article(source, title, link, date_str, excerpt):
    title = clean_text(title, 250)
    excerpt = clean_text(excerpt, 350)
    link = link.strip()
    if not title or not link: return None
    return {
        "id": link,
        "title": title,
        "excerpt": excerpt,
        "link": link,
        "date": parse_date_str(date_str),
        "category": detect_category(title, excerpt),
        "source": {"id": source["id"], "name": source["name"], "color": source["color"]},
    }

# ---------------------------------------------------------------------------
# RSS/Atom parser
# ---------------------------------------------------------------------------
def parse_feed(xml, source):
    articles = []
    is_atom = bool(re.search(r"<feed[\s>]", xml[:1000]))

    if is_atom:
        for m in re.finditer(r"<entry[^>]*>(.*?)</entry>", xml, re.DOTALL):
            e = m.group(1)
            title = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", e, re.DOTALL)
            link  = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', e) or re.search(r"<link[^>]*>([^<]+)</link>", e, re.DOTALL)
            date  = re.search(r"<published>(.*?)</published>", e, re.DOTALL) or re.search(r"<updated>(.*?)</updated>", e, re.DOTALL)
            desc  = re.search(r"<summary[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>", e, re.DOTALL) or re.search(r"<content[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</content>", e, re.DOTALL)
            a = make_article(source,
                title.group(1) if title else "",
                link.group(1) if link else "",
                date.group(1) if date else "",
                desc.group(1) if desc else "")
            if a: articles.append(a)
    else:
        for m in re.finditer(r"<item[^>]*>(.*?)</item>", xml, re.DOTALL):
            it = m.group(1)
            title = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.DOTALL)
            link  = re.search(r"<link[^>]*>([^<]+)</link>", it, re.DOTALL)
            date  = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", it, re.DOTALL)
            desc  = re.search(r"<description[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", it, re.DOTALL)
            a = make_article(source,
                title.group(1) if title else "",
                (link.group(1) if link else "").strip(),
                date.group(1) if date else "",
                desc.group(1) if desc else "")
            if a: articles.append(a)

    return articles[:MAX_PER_SOURCE]

# ---------------------------------------------------------------------------
# HTML scrapers
# ---------------------------------------------------------------------------
def scrape_anthropic(html, source):
    articles = []
    seen = set()
    # Pattern: <a href="/news/SLUG">...<div>title</div>...</a>
    for href, inner in re.findall(r'href=["\'](/news/[a-z0-9\-]+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        if href in seen or href == "/news": continue
        seen.add(href)
        # title from h1/h2/h3/strong or first decent text node
        t = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.DOTALL)
        title = strip_tags(t.group(1)) if t else ""
        if not title:
            # fallback: grab longest text span
            texts = [strip_tags(x) for x in re.findall(r">([^<]{20,})<", inner)]
            title = max(texts, key=len) if texts else ""
        if len(title) < 8: continue
        date_m = re.search(r'datetime=["\']([^"\']+)["\']', inner)
        desc_m = re.search(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)
        a = make_article(source, title, f"https://www.anthropic.com{href}",
                         date_m.group(1) if date_m else "",
                         desc_m.group(1) if desc_m else "")
        if a: articles.append(a)
    return articles[:MAX_PER_SOURCE]

def scrape_mistral(html, source):
    articles = []
    seen = set()
    for href, inner in re.findall(r'href=["\']((?:https://mistral\.ai)?/(?:fr/)?news/[^"\'?#]+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        if href in seen: continue
        seen.add(href)
        t = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.DOTALL)
        title = strip_tags(t.group(1)) if t else ""
        if len(title) < 8: continue
        full_url = href if href.startswith("http") else f"https://mistral.ai{href}"
        date_m = re.search(r'datetime=["\']([^"\']+)["\']', inner)
        desc_m = re.search(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)
        a = make_article(source, title, full_url,
                         date_m.group(1) if date_m else "",
                         desc_m.group(1) if desc_m else "")
        if a: articles.append(a)
    return articles[:MAX_PER_SOURCE]

def scrape_xai(html, source):
    articles = []
    seen = set()
    # Pattern: href="/news/SLUG"
    for href, inner in re.findall(r'href=["\'](/news/[a-z0-9\-]+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        if href in seen: continue
        seen.add(href)
        t = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.DOTALL)
        title = strip_tags(t.group(1)) if t else ""
        if not title:
            texts = [strip_tags(x) for x in re.findall(r">([^<]{20,})<", inner)]
            title = max(texts, key=len) if texts else ""
        if len(title) < 8: continue
        date_m = re.search(r'datetime=["\']([^"\']+)["\']', inner)
        desc_m = re.search(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)
        a = make_article(source, title, f"https://x.ai{href}",
                         date_m.group(1) if date_m else "",
                         desc_m.group(1) if desc_m else "")
        if a: articles.append(a)
    return articles[:MAX_PER_SOURCE]

def scrape_elevenlabs(html, source):
    articles = []
    seen = set()
    for href, inner in re.findall(r'href=["\'](/blog/[a-z0-9\-]+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        if href in seen: continue
        seen.add(href)
        # skip category pages
        if href.startswith("/blog/category") or href == "/blog": continue
        t = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.DOTALL)
        title = strip_tags(t.group(1)) if t else ""
        if not title:
            texts = [strip_tags(x) for x in re.findall(r">([^<]{20,})<", inner)]
            title = max(texts, key=len) if texts else ""
        if len(title) < 8: continue
        date_m = re.search(r'datetime=["\']([^"\']+)["\']', inner)
        desc_m = re.search(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)
        a = make_article(source, title, f"https://elevenlabs.io{href}",
                         date_m.group(1) if date_m else "",
                         desc_m.group(1) if desc_m else "")
        if a: articles.append(a)
    return articles[:MAX_PER_SOURCE]

def scrape_cohere(html, source):
    articles = []
    seen = set()
    for href, inner in re.findall(r'href=["\']((?:https://cohere\.com)?/blog/[^"\'?#]+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        if href in seen: continue
        seen.add(href)
        t = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.DOTALL)
        title = strip_tags(t.group(1)) if t else ""
        if len(title) < 8: continue
        full_url = href if href.startswith("http") else f"https://cohere.com{href}"
        date_m = re.search(r'datetime=["\']([^"\']+)["\']', inner)
        desc_m = re.search(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)
        a = make_article(source, title, full_url,
                         date_m.group(1) if date_m else "",
                         desc_m.group(1) if desc_m else "")
        if a: articles.append(a)
    return articles[:MAX_PER_SOURCE]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def fetch_source(src):
    print(f"  [{src['id']:12s}] ", end="", flush=True)
    try:
        html = fetch_url(src["url"])
        if src["type"] == "rss":
            articles = parse_feed(html, src)
        elif src["id"] == "anthropic":
            articles = scrape_anthropic(html, src)
        elif src["id"] == "mistral":
            articles = scrape_mistral(html, src)
        elif src["id"] == "xai":
            articles = scrape_xai(html, src)
        elif src["id"] == "elevenlabs":
            articles = scrape_elevenlabs(html, src)
        elif src["id"] == "cohere":
            articles = scrape_cohere(html, src)
        else:
            articles = []
        print(f"OK  {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"FAIL  {str(e)[:60]}")
        return []

def load_existing(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("articles", [])

def main():
    out_path = os.path.join(os.path.dirname(__file__), "..", "veille-data.json")
    print("=== AI Signal Feed Fetcher ===\n")

    # Fetch all sources
    fresh = []
    for src in SOURCES:
        fresh.extend(fetch_source(src))

    # Merge with existing (rolling window)
    existing = load_existing(out_path)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ROLLING_DAYS)).isoformat()

    # Index existing by id
    existing_map = {a["id"]: a for a in existing if a.get("date", "") >= cutoff or not a.get("date")}

    # Override with fresh data (preserve analysis if already present)
    for a in fresh:
        prev = existing_map.get(a["id"])
        if prev and prev.get("analysis"):
            a["analysis"] = prev["analysis"]
        existing_map[a["id"]] = a

    # ── Grok AI analysis for new articles ────────────────────────────────────
    already_analyzed = {a["id"] for a in existing if a.get("analysis")}
    fresh_ids        = {a["id"] for a in fresh}
    need_analysis    = [
        existing_map[aid] for aid in (fresh_ids - already_analyzed)
        if aid in existing_map and existing_map[aid].get("excerpt")
    ]
    # Prioritize recent articles
    need_analysis.sort(key=lambda x: x.get("date", ""), reverse=True)
    need_analysis = need_analysis[:MAX_TO_ANALYZE]

    if not GROK_API_KEY:
        print("\n[!] GROK_API_KEY not set — skipping AI analysis")
    elif need_analysis:
        print(f"\n=== Grok Analysis ({len(need_analysis)} new articles) ===")
        ok_count = 0
        for i, a in enumerate(need_analysis):
            try:
                label = (a["title"][:55] + "...") if len(a["title"]) > 55 else a["title"]
                print(f"  [{i+1:02d}/{len(need_analysis)}] {label:<58}", end=" ", flush=True)
                analysis = call_grok(a["title"], a["excerpt"], a["source"]["name"], a["category"])
                if analysis:
                    existing_map[a["id"]]["analysis"] = analysis
                    ok_count += 1
                    print("OK")
                else:
                    print("SKIP")
            except Exception as loop_err:
                print(f"LOOP_ERR({str(loop_err)[:40]})")
            if i < len(need_analysis) - 1:
                time.sleep(GROK_DELAY)
        print(f"  => {ok_count}/{len(need_analysis)} analyzed")
    else:
        print("\n[✓] No new articles to analyze")

    merged = list(existing_map.values())

    # Sort by date descending
    def sort_key(a):
        return a.get("date") or "0000"
    merged.sort(key=sort_key, reverse=True)

    # Cap total
    merged = merged[:MAX_TOTAL]

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "count": len(merged),
        "sources": len(set(a["source"]["id"] for a in merged)),
        "articles": merged,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=> {len(merged)} articles total | {output['sources']} sources | saved to veille-data.json")

if __name__ == "__main__":
    main()
