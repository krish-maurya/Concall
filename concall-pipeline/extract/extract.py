import re, collections, pymupdf
def extract_text(pdf: bytes, ocr: bool = True) -> str:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    pages = []
    for p in doc:
        t = p.get_text("text", sort=True)  # sort=True helps multi-column reading order
        if len(t.strip()) < 30 and ocr:   # image-only page -> OCR fallback (needs tesseract installed)
            try: t = p.get_textpage_ocr(full=True).extractText()
            except Exception: t = ""
        pages.append(t)
    return clean(pages)
def clean(pages):
    lines_per_page = [[l.strip() for l in p.splitlines() if l.strip()] for p in pages]
    n = len(pages)
    # lines repeated on >=40% of pages (digits normalised) are headers/footers
    SPK = re.compile(r"^[A-Za-z .]{2,40}:")  # never treat speaker turns as boilerplate
    cnt = collections.Counter(k for ls in lines_per_page for k in {re.sub(r"\d+", "#", l) for l in ls if len(l) < 90 and not SPK.match(l)})
    junk = {k for k, v in cnt.items() if n >= 4 and v >= 0.4 * n}
    out = []
    for ls in lines_per_page:
        for l in ls:
            if (len(l) < 90 and not SPK.match(l) and re.sub(r"\d+", "#", l) in junk) or re.fullmatch(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", l, re.I): continue
            out.append(l)
    text = "\n".join(out)
    text = re.sub(r"(?<=[a-z,])\n(?=[a-z])", " ", text)           # re-join wrapped lines
    text = re.sub(r"\n(?=(Moderator|Management|[A-Z][a-z]+ [A-Z][a-z]+)\s*:)", "\n\n", text)  # speaker turns
    return re.sub(r"\n{3,}", "\n\n", text).strip()
def detect_quarter(text: str):
    m = re.search(r"\bQ([1-4])\s*[-']?\s*FY\s*['-]?\s*(\d{2,4})", text, re.I)
    if m: return f"Q{m.group(1)} FY{m.group(2)[-2:]}"
    m = re.search(r"(first|second|third|fourth) quarter.{0,40}?(?:FY|financial year)\s*(?:20)?(\d{2})", text, re.I | re.S)
    if m: return f"Q{['first','second','third','fourth'].index(m.group(1).lower())+1} FY{m.group(2)}"
    return None

_M = "january february march april may june july august september october november december".split()
def detect_call_date(text: str):
    """First 'DD Month YYYY' / 'Month DD, YYYY' in the opening of the transcript -> ISO date."""
    head = text[:4000]; mon = "|".join(m.capitalize() for m in _M) + "|" + "|".join(m[:3].capitalize() for m in _M)
    cands = []
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s,.\-]+({mon})[a-z]*\.?[\s,.\-]+(\d{{4}})", head): cands.append((m.start(), m.group(3), m.group(2), m.group(1)))
    for m in re.finditer(rf"\b({mon})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", head): cands.append((m.start(), m.group(3), m.group(1), m.group(2)))
    for _, y, mo, d in sorted(cands):
        mi = [x[:3] for x in _M].index(mo[:3].lower()) + 1
        if 1 <= int(d) <= 31: return f"{y}-{mi:02d}-{int(d):02d}"
    return None
