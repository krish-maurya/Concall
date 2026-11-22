# Concall Pipeline
Real-time pipeline: watches NSE (and BSE) for earnings-call **transcripts**, extracts the PDF text, builds a grounded structured summary with an LLM, and serves it through a UI, REST API and WebSocket.

    watcher -> extract -> summarize (map-reduce) -> server (SQLite + FastAPI + /ws + UI)

## Setup & run
    python -m venv .venv && source .venv/bin/activate     # Windows Git Bash: source .venv/Scripts/activate
    pip install -r requirements.txt
    cp .env.example .env     # set LLM_API_KEY (+ LLM_MODEL); never commit .env
    python run.py            # watcher + UI + WebSocket -> http://localhost:8000

Pages: `/` summaries, `/live` live feed of every LLM reply as it arrives.
Optional OCR for scanned PDFs: install Tesseract.

## Endpoints
| | |
|---|---|
| `GET /api/summaries`, `/api/summaries/{id}`, `/api/summaries/{id}/md` | stored summaries |
| `POST /api/backfill?days=45` | pull historical transcripts for the watchlist |
| `GET /api/progress?since=N` | recent pipeline events (chunk/merge replies) |
| `WS /ws` | each finished summary, pushed live (the React UI's **WebSocket** button shows this URL) |
| `WS /ws/live` | every pipeline step + raw LLM reply |

## Test
    python -m pytest -q
    pip install websockets && python -m websockets ws://localhost:8000/ws
    python tools/export_samples.py     # writes samples/<company>/{transcript.txt,summary.json,summary.md}

## Design decisions
- **Ingest:** browser-like session with warm-up cookies, request throttling, retry with backoff, session refresh on 401/429/5xx. 403 (WAF block) is reported once instead of retried. One exchange failing never stops the other. `SOURCES=nse` disables BSE.
- **Detection:** keep filings whose text says "transcript"; skip audio-only and intimation filings. Watchlist by name fragment (`WATCHLIST`), optional per-symbol NSE queries (`SYMBOLS`).
- **Dedupe (3 layers):** URL seen; normalised company + *call date* (dates normalised to ISO across NSE/BSE formats); SHA-256 of extracted text. The same call on NSE and BSE is summarised once.
- **Extract:** PyMuPDF, reading-order sort, headers/footers removed by cross-page repetition (speaker lines protected), per-page OCR fallback. Call date and quarter are detected from the transcript text; the filing date is kept separately (`filing_date`).
- **Summarize (map-reduce):** ~4k-char chunks -> per-chunk extraction -> hierarchical merge sized to the provider's token-per-minute budget (a limiter paces calls). Chunk results are cached on disk so a failed run resumes. Truncated JSON is repaired; truncated replies are retried with a "be shorter" hint.
- **No hallucination:** prompts allow only the provided text; every key metric carries entity, period and a verbatim quote. Each metric is verified in code: ✅ quote found in transcript *and* the number is inside the quote; 🟡 number exists in the transcript but the quote does not match (check manually); ⚠️ neither.
- **Schema additions:** `filing_date`, `tone`, metric `entity`/`period`/`quote`/`verified`, `chunks_processed`.
- **Provider-agnostic:** any OpenAI-compatible endpoint (Groq, Gemini, OpenRouter). **A real `LLM_API_KEY` is required**: there is no mock mode and the server refuses to start without one.
- **Which companies (`WATCH_MODE`):** the exchange feeds are always scanned in full (a couple of cheap HTTP calls per poll); the cost is the LLM, roughly 15-20 calls (~45k input + ~15k output tokens) per transcript. `watchlist` mode (default when `WATCHLIST`/`SYMBOLS` is set) summarises only your 5-10 companies, as the assignment scope says. `all` mode summarises every transcript found, capped by `MAX_SUMMARIES_PER_DAY` (default 40) so spend cannot run away. Newest filings are processed first; anything over the cap waits for the next day.
- **Clean shutdown:** a stop flag lets worker threads exit on Ctrl+C.

## Known limitations
- **BSE is blocked** by its WAF (HTTP 403) in my environment even with a warmed session; the code path is implemented but unverified. NSE carries the same filings.
- Free-tier LLM limits make a transcript take ~5-10 min; several companies are processed one after another. Daily token caps can interrupt a long backfill (switch `LLM_MODEL` or provider, cached chunks are reused).
- To fit the token budget, intermediate merges keep only the top 3 items per list, so detail can be lost on long calls.
- Call date comes from the first date-like string in the transcript's opening; it falls back to the filing date.
- 🟡/⚠️ metrics need a human check. Verification proves the quote exists, not that the model interpreted it correctly.
- Polling, not push (latency <= `POLL_SECONDS`). No auth on WebSockets. XBRL not parsed. Audio-only filings are skipped, not tracked.

## With more time
Parse XBRL; durable job queue and parallel workers; span-level citations for every claim; eval set of hand-written summaries; BSE via a compliant data feed; auth + Docker; sentiment trend across quarters.
