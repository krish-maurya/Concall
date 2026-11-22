import hashlib, asyncio, logging
import db
import os, pathlib, config
from extract.extract import extract_text, detect_quarter, detect_call_date
from summarize.summarize import summarize, to_markdown, set_context, emit
from watcher.watcher import dedupe_key
log = logging.getLogger("pipeline")

def process_sync(item, pdf: bytes):
    """extract -> summarize -> store. Returns saved record or None if duplicate."""
    set_context(company=item.get('company'), source=item.get('source'))
    emit('started', url=item.get('url'), pdf_bytes=len(pdf))
    text = extract_text(pdf)
    emit('extracted', chars=len(text))
    if len(text) < 500: raise ValueError("no usable text (scanned PDF without OCR, or empty)")
    h = hashlib.sha256(text.encode()).hexdigest()
    item = {**item, "filing_date": item["date"], "date": detect_call_date(text) or item["date"]}  # call date from the transcript
    key = dedupe_key(item)
    if db.exists(key, h): log.info("duplicate skipped: %s", key); emit('duplicate'); return None  # same call on NSE and BSE
    item = {**item, "quarter": detect_quarter(text)}
    s = summarize(text, item)
    md = to_markdown(s)
    s["id"] = db.save(key, h, s, md)
    d = pathlib.Path(os.path.dirname(config.DB_PATH) or ".") / "transcripts"; d.mkdir(parents=True, exist_ok=True)
    (d / f"{s['id']}.txt").write_text(text, encoding="utf-8")  # raw cleaned transcript for samples
    emit('saved', id=s['id'])
    return s

async def make_process(broadcast):
    async def process(item, pdf):
        s = await asyncio.to_thread(process_sync, item, pdf)
        if s: await broadcast(s)
    return process
