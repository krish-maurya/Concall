"""NSE + BSE announcement fetchers -> normalized dicts {company, symbol, scrip, date, url, source, text}."""
import re, logging
import config
from datetime import date, timedelta
from .http import Throttled
log = logging.getLogger("watcher")
NSE = Throttled({"Referer": "https://www.nseindia.in/companies-listing/corporate-filings-announcements"}, "https://www.nseindia.in", 1.5)
BSE = Throttled({"Origin": "https://www.bseindia.com", "Referer": "https://www.bseindia.com/corporates/ann.html", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site"}, "https://www.bseindia.com/corporates/ann.html", 1.0)
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
def to_iso(s):
    """NSE '19-Nov-2026 20:23:07', BSE '2026-11-19T..', '19-11-2026' -> '2026-11-19'."""
    s = (s or "").strip()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", s): return m.group(0)
    if m := re.search(r"(\d{1,2})-([A-Za-z]{3})[a-z]*-(\d{4})", s):
        return f"{m.group(3)}-{MONTHS.get(m.group(2).lower(), 0):02d}-{int(m.group(1)):02d}"
    if m := re.search(r"(\d{2})-(\d{2})-(\d{4})", s): return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return s[:10]

IS_TRANSCRIPT = re.compile(r"transcript", re.I)
IS_AUDIO_ONLY = re.compile(r"audio|recording", re.I)

def is_transcript(text: str) -> bool:
    """Keep concall *transcripts*; skip intimations, audio-only recordings and everything else."""
    return bool(IS_TRANSCRIPT.search(text or "")) and not (IS_AUDIO_ONLY.search(text or "") and "transcript" not in (text or "").lower())

def fetch_nse(days: int):
    f, t = (date.today() - timedelta(days=days)).strftime("%d-%m-%Y"), date.today().strftime("%d-%m-%Y")
    rows = []
    for sym in (config.SYMBOLS if config.WATCH_MODE == "watchlist" else []) or [None]:  # per-symbol queries avoid the global feed's row cap
        params = {"index": "equities", "from_date": f, "to_date": t, **({"symbol": sym} if sym else {})}
        got = NSE.get("https://www.nseindia.in/api/corporate-announcements", params=params).json()
        rows += got if isinstance(got, list) else []
    out = []
    for r in rows:
        blob = f"{r.get('desc','')} {r.get('attchmntText','')}"
        if is_transcript(blob) and r.get("attchmntFile"):
            out.append(dict(company=r.get("sm_name") or r.get("symbol"), symbol=r.get("symbol"), scrip=None,
                            date=to_iso(r.get("an_dt")), url=r["attchmntFile"], source="NSE", text=blob))
    return out

def fetch_bse(days: int):
    f, t = (date.today() - timedelta(days=days)).strftime("%Y%m%d"), date.today().strftime("%Y%m%d")
    url = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
    out = []
    for page in (1, 2, 3):
        r = BSE.get(url, params={"pageno": page, "strCat": "Company Update", "subcategory": "Earnings Call Transcript",
                                 "strPrevDate": f, "strToDate": t, "strScrip": "", "strSearch": "P", "strType": "C"})
        if r.status_code == 403: raise RuntimeError("BSE API 403: blocked by BSE Akamai/WAF (NSE remains available)")
        r.raise_for_status(); d = r.json()
        rows = d.get("Table") or []
        for r in rows:
            blob = f"{r.get('NEWSSUB','')} {r.get('HEADLINE','')}"
            if r.get("ATTACHMENTNAME") and is_transcript(blob):
                out.append(dict(company=r.get("SLONGNAME"), symbol=None, scrip=str(r.get("SCRIP_CD")), date=to_iso(r.get("NEWS_DT")),
                                url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/" + r["ATTACHMENTNAME"], source="BSE", text=blob))
        if len(rows) < 50: break
    return out

def download_pdf(item) -> bytes:
    cl = NSE if item["source"] == "NSE" else BSE
    r = cl.get(item["url"], headers={"Accept": "application/pdf,*/*"})
    if not r.content.startswith(b"%PDF"): raise ValueError("not a PDF (blocked or HTML error page)")
    return r.content
