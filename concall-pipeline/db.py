import sqlite3, json, threading
import config
_lock = threading.Lock()
def _c():
    c = sqlite3.connect(config.DB_PATH, check_same_thread=False); c.row_factory = sqlite3.Row; return c
def init():
    import os; os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    with _lock, _c() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY, dedupe_key TEXT UNIQUE,
          text_hash TEXT UNIQUE, company TEXT, quarter TEXT, call_date TEXT, source TEXT, url TEXT,
          json TEXT, md TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("CREATE TABLE IF NOT EXISTS seen(url TEXT PRIMARY KEY)")

def seed_from_samples(samples_dir):
    """Populate an empty database from committed sample outputs."""
    import hashlib
    import os
    import pathlib

    samples_dir = pathlib.Path(samples_dir)
    if not samples_dir.is_dir():
        return 0

    with _lock, _c() as c:
        if c.execute("SELECT 1 FROM summaries LIMIT 1").fetchone():
            return 0

    inserted = 0
    for summary_path in sorted(samples_dir.glob("*/summary.json")):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            md_path = summary_path.with_name("summary.md")
            md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(summary, dict):
            continue

        source_url = str(summary.get("source_url") or "")
        company = str(summary.get("company") or "Unknown company")
        quarter = str(summary.get("quarter") or "")
        call_date = str(summary.get("call_date") or summary.get("filing_date") or "")
        source = str(summary.get("source") or "")
        raw_json = json.dumps(summary, ensure_ascii=False)
        dedupe_key = f"{company}|{call_date}".strip().lower()
        text_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        with _lock, _c() as c:
            try:
                c.execute(
                    """INSERT INTO summaries
                       (dedupe_key,text_hash,company,quarter,call_date,source,url,json,md)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (dedupe_key, text_hash, company, quarter, call_date, source, source_url, raw_json, md),
                )
            except sqlite3.IntegrityError:
                continue
            inserted += 1
    return inserted
def seen(url):
    with _lock, _c() as c: return c.execute("SELECT 1 FROM seen WHERE url=?", (url,)).fetchone() is not None
def mark_seen(url):
    with _lock, _c() as c: c.execute("INSERT OR IGNORE INTO seen VALUES(?)", (url,))
def exists(dedupe_key=None, text_hash=None):
    with _lock, _c() as c:
        return c.execute("SELECT 1 FROM summaries WHERE dedupe_key=? OR text_hash=?", (dedupe_key, text_hash)).fetchone() is not None
def save(dedupe_key, text_hash, s, md):
    with _lock, _c() as c:
        cur = c.execute("INSERT INTO summaries(dedupe_key,text_hash,company,quarter,call_date,source,url,json,md) VALUES(?,?,?,?,?,?,?,?,?)",
          (dedupe_key, text_hash, s.get("company"), s.get("quarter"), s.get("call_date"), s.get("source"), s.get("source_url"), json.dumps(s), md))
        return cur.lastrowid
def count_today():
    """Summaries created today (UTC) - used by the daily LLM-cost cap."""
    with _lock, _c() as c:
        return c.execute("SELECT COUNT(*) FROM summaries WHERE date(created)=date('now')").fetchone()[0]
def list_all():
    with _lock, _c() as c:
        return [dict(r) for r in c.execute("SELECT id,company,quarter,call_date,source,created FROM summaries ORDER BY id DESC")]
def get(i):
    with _lock, _c() as c:
        r = c.execute("SELECT * FROM summaries WHERE id=?", (i,)).fetchone()
        return dict(r) if r else None
