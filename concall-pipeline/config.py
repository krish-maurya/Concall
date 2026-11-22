import os
from dotenv import load_dotenv
load_dotenv()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "120"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "3"))
WATCHLIST = [w.strip().lower() for w in os.getenv("WATCHLIST", "").split(",") if w.strip()]
DB_PATH = os.getenv("DB_PATH", "data/concall.db")
LLM_TPM = int(os.getenv("LLM_TPM", "7000"))          # tokens/min budget (Groq free tier ~8000)
LLM_MAX_OUT = int(os.getenv("LLM_MAX_OUT", "1200"))
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "4000"))
SOURCES = [x.strip().lower() for x in os.getenv("SOURCES", "nse,bse").split(",")]
SYMBOLS = [x.strip().upper() for x in os.getenv("SYMBOLS", "").split(",") if x.strip()]  # optional NSE symbols, e.g. TCS,INFY

# --- What to process -------------------------------------------------------------
# "watchlist": only companies in WATCHLIST / SYMBOLS (cheap, matches the 5-10 company scope)
# "all":       every concall transcript on NSE/BSE (scanning is free, but each one costs LLM tokens)
# Unset => "watchlist" if a WATCHLIST/SYMBOLS is given, otherwise "all" (the previous behaviour).
WATCH_MODE = os.getenv("WATCH_MODE", "").strip().lower() or ("watchlist" if (WATCHLIST or SYMBOLS) else "all")
if WATCH_MODE not in ("watchlist", "all"):
    raise ValueError("WATCH_MODE must be 'watchlist' or 'all'")
if WATCH_MODE == "watchlist" and not (WATCHLIST or SYMBOLS):
    raise ValueError("WATCH_MODE=watchlist needs WATCHLIST or SYMBOLS (or set WATCH_MODE=all)")
# Safety valve on LLM spend: max new summaries per UTC day. 0 = unlimited.
# Defaults to 40 in "all" mode so an unattended run cannot burn the whole API budget.
MAX_SUMMARIES_PER_DAY = int(os.getenv("MAX_SUMMARIES_PER_DAY") or ("40" if WATCH_MODE == "all" else "0"))  # empty value in .env => default
