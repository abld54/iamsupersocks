"""Create ai_signal_articles table on OuiHeberg PostgreSQL."""
import psycopg2, os

DB = dict(
    host=os.environ.get("COGEFOX_DB_HOST", "45.140.164.244"),
    port=int(os.environ.get("COGEFOX_DB_PORT", 25543)),
    dbname=os.environ.get("COGEFOX_DB_NAME", "prediction_api"),
    user=os.environ.get("COGEFOX_DB_USER", "ouiheberg"),
    password=os.environ.get("COGEFOX_DB_PASS", ""),
)

CREATE = """
CREATE TABLE IF NOT EXISTS ai_signal_articles (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    excerpt          TEXT,
    link             TEXT,
    date             TIMESTAMPTZ,
    category         TEXT,
    source_id        TEXT,
    source_name      TEXT,
    source_color     TEXT,
    analysis_signal  TEXT,
    analysis_summary TEXT,
    analysis_context TEXT,
    analysis_critique TEXT,
    analysis_themes  JSONB,
    analysis_model   TEXT,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_signal_date     ON ai_signal_articles (date DESC);
CREATE INDEX IF NOT EXISTS idx_ai_signal_source   ON ai_signal_articles (source_id);
CREATE INDEX IF NOT EXISTS idx_ai_signal_category ON ai_signal_articles (category);
"""

conn = psycopg2.connect(**DB)
cur = conn.cursor()
cur.execute(CREATE)
conn.commit()
cur.execute("SELECT COUNT(*) FROM ai_signal_articles")
count = cur.fetchone()[0]
conn.close()
print(f"Table ai_signal_articles ready — {count} rows existing")
