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
