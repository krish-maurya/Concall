import asyncio, json, logging, pathlib, itertools, collections
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import db, config, pipeline
from summarize import summarize as S
from watcher import watcher, sources
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
STATIC = pathlib.Path(__file__).parent / "static"

class Hub:
    def __init__(self): self.clients = set()
    async def broadcast(self, msg):
        for ws in list(self.clients):
            try: await ws.send_text(json.dumps(msg))
            except Exception: self.clients.discard(ws)
hub = Hub(); live = Hub()
events = collections.deque(maxlen=500); _seq = itertools.count(1)

@asynccontextmanager
async def lifespan(app):
    db.init(); S.STOP.clear()
    loop = asyncio.get_running_loop()
    def on_event(ev):  # called from worker threads
        ev["seq"] = next(_seq); events.append(ev)
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(live.broadcast(ev)))
    S.listeners.append(on_event)
    task = None
    if not getattr(app.state, "no_watcher", False):
        task = asyncio.create_task(watcher.run(await pipeline.make_process(hub.broadcast)))
    yield
    S.STOP.set()  # tell worker threads to stop so the process can exit
    S.listeners.remove(on_event)
    if task: task.cancel()

app = FastAPI(title="Concall Pipeline", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/")
def index(): return FileResponse(STATIC / "index.html")
@app.get("/live")
def live_page(): return FileResponse(STATIC / "live.html")
@app.get("/api/progress")
def progress(since: int = 0): return [e for e in events if e["seq"] > since]
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    for e in list(events): await ws.send_text(json.dumps(e))  # backlog
    live.clients.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: live.clients.discard(ws)
@app.get("/api/summaries")
def list_(): return db.list_all()
@app.get("/api/summaries/{i}")
def one(i: int):
    r = db.get(i)
    if not r: raise HTTPException(404)
    try:
        summary = json.loads(r["json"])
    except (json.JSONDecodeError, TypeError):
        summary = {}
    if not isinstance(summary, dict):
        summary = {}

    return {
        "id": r["id"],
        "company": r["company"],
        "quarter": r["quarter"],
        "call_date": r["call_date"],
        "source": r["source"],
        "source_url": r["url"],
        **summary,
        "id": r["id"],
        "company": summary.get("company") or r["company"],
        "quarter": summary.get("quarter") or r["quarter"],
        "call_date": summary.get("call_date") or r["call_date"],
        "source": summary.get("source") or r["source"],
        "source_url": summary.get("source_url") or r["url"],
    }
@app.get("/api/summaries/{i}/md", response_class=PlainTextResponse)
def md(i: int):
    r = db.get(i)
    if not r: raise HTTPException(404)
    return r["md"]
@app.post("/api/backfill")
async def backfill(days: int = 30):
    """Pull historical transcripts for the last N days (watchlist applies)."""
    old = config.LOOKBACK_DAYS; config.LOOKBACK_DAYS = days
    try: items = await asyncio.to_thread(watcher.poll_once)
    finally: config.LOOKBACK_DAYS = old
    proc = await pipeline.make_process(hub.broadcast); done = 0
    for it in items:
        try: await proc(it, await asyncio.to_thread(sources.download_pdf, it)); db.mark_seen(it["url"]); done += 1
        except Exception as e: logging.getLogger("backfill").error("%s: %s", it["url"], e)
    return {"found": len(items), "processed": done}
@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept(); hub.clients.add(ws)
    try:
        while True: await ws.receive_text()  # keep-alive; clients may ping
    except WebSocketDisconnect: hub.clients.discard(ws)
