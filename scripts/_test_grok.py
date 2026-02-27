#!/usr/bin/env python3
"""Quick test of Grok API key."""
import json, os, urllib.request, urllib.error

if hasattr(__import__('sys').stdout, 'reconfigure'):
    __import__('sys').stdout.reconfigure(encoding='utf-8', errors='replace')

key = os.environ.get("GROK_API_KEY", "")
if not key:
    print("ERROR: GROK_API_KEY not set")
    exit(1)

body = json.dumps({
    "model": "grok-3-mini",
    "messages": [{"role": "user", "content": "Analyse cet article IA en JSON: {\"signal\": \"une phrase\", \"summary\": \"deux phrases\", \"context\": \"contexte\", \"critique\": \"critique\", \"themes\": [\"IA\", \"Modeles\"]}. Article: OpenAI sort GPT-5 avec des capacites de raisonnement avancees."}],
    "response_format": {"type": "json_object"},
    "max_tokens": 300,
    "temperature": 0.4,
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.x.ai/v1/chat/completions",
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        resp = json.loads(r.read())
    text = resp["choices"][0]["message"]["content"]
    parsed = json.loads(text)
    print("KEY OK - Grok works")
    print(f"signal:   {parsed.get('signal', '')[:80]}")
    print(f"context:  {parsed.get('context', '')[:80]}")
    print(f"critique: {parsed.get('critique', '')[:80]}")
    print(f"themes:   {parsed.get('themes', [])}")
except urllib.error.HTTPError as e:
    print(f"HTTP ERROR {e.code}: {e.read().decode()[:200]}")
except Exception as e:
    print(f"ERROR: {e}")
