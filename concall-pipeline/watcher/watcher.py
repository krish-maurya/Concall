import asyncio, logging, re
import config, db
from . import sources
log = logging.getLogger("watcher")

def wanted(item):
    if config.WATCH_MODE == "all": return True
    n = (item["company"] or "").lower()
    return (item.get("symbol") or "").upper() in config.SYMBOLS or any(w in n for w in config.WATCHLIST)

def norm(name): return re.sub(r"[^a-z0-9]", "", (name or "").lower().replace("limited", "").replace("ltd", ""))
def dedupe_key(item): return f"{norm(item['company'])}|{item['date'][:10]}"

def poll_once():
    items = []
    fns = {"nse": sources.fetch_nse, "bse": sources.fetch_bse}
    for fn in [fns[x] for x in config.SOURCES if x in fns]:
        try: items += fn(config.LOOKBACK_DAYS)
        except Exception as e: log.warning("%s failed: %s", fn.__name__, e)  # one exchange down != pipeline down
    items = [i for i in items if wanted(i) and not db.seen(i["url"]) and not db.exists(dedupe_key(i))]
    return sorted(items, key=lambda i: i["date"], reverse=True)  # newest first, so a daily cap drops the oldest

async def run(process):
    """process(item, pdf_bytes) is the pipeline callback. Runs forever."""
    while True:
        try:
            for item in await asyncio.to_thread(poll_once):
                if config.MAX_SUMMARIES_PER_DAY and db.count_today() >= config.MAX_SUMMARIES_PER_DAY:
                    log.warning("daily cap of %d summaries reached; remaining filings wait for tomorrow", config.MAX_SUMMARIES_PER_DAY)
                    break  # items stay unseen, so they are picked up again after the cap resets
                try:
                    pdf = await asyncio.to_thread(sources.download_pdf, item)
                    await process(item, pdf)
                    db.mark_seen(item["url"])
                except Exception as e: log.error("item failed %s: %s", item["url"], e)
        except Exception as e: log.error("poll loop error: %s", e)
        await asyncio.sleep(config.POLL_SECONDS)
