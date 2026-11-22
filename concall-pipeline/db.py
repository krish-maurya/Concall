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
def list_all():
    with _lock, _c() as c:
        return [dict(r) for r in c.execute("SELECT id,company,quarter,call_date,source,created FROM summaries ORDER BY id DESC")]
def get(i):
    with _lock, _c() as c:
        r = c.execute("SELECT * FROM summaries WHERE id=?", (i,)).fetchone()
        return dict(r) if r else None
