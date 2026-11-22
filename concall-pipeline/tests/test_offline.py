"""Offline tests (no network, no API key): python -m pytest -q"""
import os, sys, json, pymupdf
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = "/tmp/test_concall.db"; os.environ["LLM_API_KEY"] = ""
if os.path.exists("/tmp/test_concall.db"): os.remove("/tmp/test_concall.db")
import db, pipeline
from fastapi.testclient import TestClient
from server.app import app
from extract.extract import detect_quarter
from summarize.summarize import chunk, verify_metrics
from watcher.sources import is_transcript

def make_pdf():
    d = pymupdf.open()
    for p in range(6):
        pg = d.new_page(); y = 60
        pg.insert_text((50, 30), "ACME Ltd - Q1 FY26 Earnings Call Transcript", fontsize=9)
        body = "Moderator: Welcome to the Q1 FY26 earnings call of ACME Ltd.\nManagement: Revenue grew 12 percent to Rs 4,500 crore this quarter and margins were stable. " * 6
        for line in body.split("\n"):
            pg.insert_text((50, y), line[:95], fontsize=10); y += 14
        pg.insert_text((280, 820), f"Page {p+1}", fontsize=8)
    return d.tobytes()

ITEM = dict(company="ACME Ltd", symbol="ACME", scrip="500001", date="2025-07-24", url="https://x/y.pdf", source="BSE")

def test_filters():
    assert is_transcript("Transcript of Earnings Call") and not is_transcript("Audio recording of earnings call") and not is_transcript("Board meeting")
def test_quarter_chunk_verify():
    assert detect_quarter("the Q1 FY26 call") == "Q1 FY26"
    assert len(chunk(("x" * 500 + "\n\n") * 100)) > 3
    s = verify_metrics({"key_metrics": [{"value": "Rs 4,500 crore"}, {"value": "99%"}]}, "revenue 4,500 crore")
    assert [m["verified"] for m in s["key_metrics"]] == [True, False]
def test_pipeline_dedupe_api_ws():
    db.init(); pdf = make_pdf()
    s = pipeline.process_sync(ITEM, pdf)
    assert s and s["quarter"] == "Q1 FY26" and "Page" not in db.get(s["id"])["md"]
    assert pipeline.process_sync({**ITEM, "source": "NSE"}, pdf) is None  # cross-exchange dup
    app.state.no_watcher = True
    with TestClient(app) as c:
        assert c.get("/api/summaries").json()[0]["company"] == "ACME Ltd"
        assert c.get(f"/api/summaries/{s['id']}").json()["json"]["company"] == "ACME Ltd"
        assert "TL;DR" in c.get(f"/api/summaries/{s['id']}/md").text
        assert c.get("/").status_code == 200
        with c.websocket_connect("/ws") as ws:
            import asyncio; from server.app import hub
            asyncio.get_event_loop_policy()  # ws connected
            assert len(hub.clients) == 1

def test_chunk_oversized_paragraph(monkeypatch):
    from summarize import summarize as S
    cs = S.chunk("word " * 5000, size=1000)
    assert len(cs) >= 10 and all(len(c) <= 1000 for c in cs)
def test_events_emitted():
    from summarize import summarize as S
    got = []; S.listeners.append(got.append)
    S.set_context(company="X"); S.emit("chunk_done", index=1, total=2, reply={"a": 1})
    S.listeners.remove(got.append) if False else None
    assert got and got[0]["company"] == "X" and got[0]["reply"] == {"a": 1}
