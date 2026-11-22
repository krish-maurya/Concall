import asyncio, logging, re
import config, db
from . import sources
log = logging.getLogger("watcher")

def wanted(item):
    if not config.WATCHLIST: return True
    n = (item["company"] or "").lower()
    return any(w in n for w in config.WATCHLIST)

def norm(name): return re.sub(r"[^a-z0-9]", "", (name or "").lower().replace("limited", "").replace("ltd", ""))
def dedupe_key(item): return f"{norm(item['company'])}|{item['date'][:10]}"

def poll_once():
    items = []
    fns = {"nse": sources.fetch_nse, "bse": sources.fetch_bse}
    for fn in [fns[x] for x in config.SOURCES if x in fns]:
        try: items += fn(config.LOOKBACK_DAYS)
        except Exception as e: log.warning("%s failed: %s", fn.__name__, e)  # one exchange down != pipeline down
    return [i for i in items if wanted(i) and not db.seen(i["url"]) and not db.exists(dedupe_key(i))]

async def run(process):
    """process(item, pdf_bytes) is the pipeline callback. Runs forever."""
    while True:
        try:
            for item in await asyncio.to_thread(poll_once):
                try:
                    pdf = await asyncio.to_thread(sources.download_pdf, item)
                    await process(item, pdf)
                    db.mark_seen(item["url"])
                except Exception as e: log.error("item failed %s: %s", item["url"], e)
        except Exception as e: log.error("poll loop error: %s", e)
        await asyncio.sleep(config.POLL_SECONDS)
