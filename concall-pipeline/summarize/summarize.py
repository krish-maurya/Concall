"""Map-reduce summarizer. MAP: per-chunk fact extraction with verbatim quotes. REDUCE: merge into fixed schema.
Anti-hallucination: grounded prompts + post-hoc check that every number in key_metrics exists in the transcript."""
import json, re, time, logging, httpx, threading, textwrap, contextvars
import config
log = logging.getLogger("summarize")

# ---- shutdown flag + live event hooks ----
STOP = threading.Event()
class Stopped(Exception): pass
def _sleep(x):
    if STOP.wait(x): raise Stopped()
listeners = []            # callables taking one event dict (the server registers one)
_ctx = contextvars.ContextVar("ctx", default={})
def set_context(**kw): _ctx.set(kw)
def emit(kind, **kw):
    ev = {"ts": time.time(), "kind": kind, **_ctx.get(), **kw}
    for f in listeners:
        try: f(ev)
        except Exception: log.exception("listener failed")
CHUNK_CHARS = config.CHUNK_CHARS

SCHEMA = {"tldr": [], "management_commentary": [], "guidance": [], "segment_performance": [{"segment": "", "notes": ""}],
          "key_metrics": [{"metric": "", "entity": "", "period": "", "value": "", "context": "", "quote": ""}],
          "notable_qa": [{"question": "", "answer": "", "asked_by": "", "answered_by": ""}], "risks": [], "tone": {"label": "", "reason": ""}}
RULES = "Use ONLY the provided text. Never invent or infer numbers, names or facts. If something is not stated, omit it. Output JSON only."

def chunk(text, size=None):
    size = size or config.CHUNK_CHARS
    if not text or not text.strip(): return []
    chunks, cur = [], ""
    for p in text.split("\n\n"):
        pieces = [p] if len(p) + 2 <= size else textwrap.wrap(p, size - 2, break_long_words=True, replace_whitespace=False)
        for piece in pieces:
            if cur and len(cur) + len(piece) + 2 > size: chunks.append(cur.rstrip()); cur = ""
            cur += piece + "\n\n"
    if cur.strip(): chunks.append(cur.rstrip())
    return chunks

_window = []  # (timestamp, tokens) of recent requests, for free-tier TPM limits

def _budget_wait(est):
    while True:
        now = time.time(); _window[:] = [(t, n) for t, n in _window if now - t < 60]
        used = sum(n for _, n in _window)
        if used + est <= config.LLM_TPM or not _window: return
        w = max(1, 60 - (now - _window[0][0]) + 1); emit("rate_wait", seconds=round(w), reason=f"{used}+{est} tokens would exceed LLM_TPM={config.LLM_TPM}"); _sleep(w)

def llm(system, user, retries=5, max_out=None):
    if STOP.is_set(): raise Stopped()
    if not config.LLM_API_KEY: raise RuntimeError("LLM_API_KEY is not set - refusing to produce a summary without a real LLM")
    max_out = max_out or config.LLM_MAX_OUT
    body = {"model": config.LLM_MODEL, "temperature": 0.1, "max_tokens": max_out,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if "gpt-oss" in config.LLM_MODEL: body["reasoning_effort"] = "low"
    est = int((len(system) + len(user)) / 3.2) + max_out
    if est > config.LLM_TPM: raise RuntimeError(f"request ~{est} tokens exceeds LLM_TPM={config.LLM_TPM}; lower CHUNK_CHARS/LLM_MAX_OUT")
    for i in range(retries):
        try:
            _budget_wait(est); entry = [time.time(), est]; _window.append(tuple(entry))
            r = httpx.post(config.LLM_BASE_URL.rstrip("/") + "/chat/completions", timeout=180,
                headers={"Authorization": f"Bearer {config.LLM_API_KEY}"}, json=body)
            if r.status_code == 429 or r.status_code >= 500:
                _sleep(float(r.headers.get("retry-after", 2 ** (i + 3)))); continue
            if 400 <= r.status_code < 500:
                raise RuntimeError(f"LLM HTTP {r.status_code} model={config.LLM_MODEL}: {r.text[:300]}")
            d = r.json(); used = (d.get("usage") or {}).get("total_tokens")
            if used: _window[-1] = (_window[-1][0], used)  # replace estimate with real usage
            ch = d["choices"][0]
            try: return parse_json(ch["message"]["content"] or "")
            except ValueError:
                if ch.get("finish_reason") == "length":  # output truncated: ask for a shorter answer next time
                    body["messages"][1]["content"] = user + "\n\nIMPORTANT: your last answer was cut off. Be much shorter: at most 3 items per list."
                    log.warning("output truncated at max_tokens=%d", max_out)
                raise
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("llm attempt %d failed: %s", i + 1, e); emit("llm_retry", attempt=i + 1, error=str(e)[:200]); _sleep(2 if "truncated" not in str(e) else 0)
    raise RuntimeError("LLM failed after retries")

def repair_json(s):
    """Close a truncated JSON document at the last complete element."""
    stack, in_str, esc, cands = [], False, False, []
    for i, ch in enumerate(s):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in "{[": stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack: stack.pop()
            cands.append(s[: i + 1] + "".join(reversed(stack)))
        elif ch == ",": cands.append(s[:i] + "".join(reversed(stack)))
    for c in reversed(cands[-40:]):
        try: return json.loads(c)
        except json.JSONDecodeError: continue
    raise ValueError("unrepairable JSON")

def parse_json(s):
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    try: return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try: return json.loads(m.group(0))
            except json.JSONDecodeError: pass
        try: return repair_json(s[s.find("{"):])
        except ValueError: raise ValueError("no valid JSON in LLM output")

def _map_chunk(c, i, n):
    return llm(f"You extract facts from part {i+1}/{n} of an Indian earnings-call transcript. {RULES}",
        f"Return JSON with keys {json.dumps(SCHEMA)}. For key_metrics give: entity (Consolidated / JLR / India PV / a segment...), period (e.g. Q2 FY27, H1 FY27, FY28 target) and a verbatim 'quote' (max 25 words) that CONTAINS the number. Never label a segment's number as consolidated. For guidance, start each item with entity and period. For notable_qa use the analyst or questioner's name and firm for asked_by. Use the named management executive or speaker who gives the answer for answered_by; if no person is named, use 'Management'. Keep asked_by and answered_by names. Empty lists if nothing relevant.\n\nTEXT:\n{c}")

import hashlib, os, pathlib
def map_chunk(c, i, n):
    """Disk-cached so a failed run resumes instead of redoing every chunk."""
    d = pathlib.Path(os.path.dirname(config.DB_PATH) or ".") / "cache"; d.mkdir(parents=True, exist_ok=True)
    f = d / (hashlib.sha1((config.LLM_MODEL + c).encode()).hexdigest() + ".json")
    cached = f.exists()
    r = json.loads(f.read_text()) if cached else _map_chunk(c, i, n)
    if not cached: f.write_text(json.dumps(r))
    emit("chunk_done", index=i + 1, total=n, cached=cached, reply=r); return r

def _merge(parts, final=False):
    lim = "max 8 items per list, max 6 Q&As, max 10 key_metrics" if final else "max 3 items per list, max 4 key_metrics, max 2 Q&As, each item under 30 words; keep entity, period and verbatim quote for every key_metric; keep asked_by and answered_by names"
    r = llm(f"You merge partial extractions of ONE earnings call into a summary. {RULES} Deduplicate; keep the sharpest items; tldr = 3-5 short lines; {lim}; each item under 40 words; keep entity, period and verbatim quote for every key_metric; keep asked_by and answered_by names.",
        f"Return JSON with exactly these keys: {json.dumps(SCHEMA)}. tone.label is one of positive/neutral/cautious/negative with a reason grounded in the text.\n\nPARTS:\n{json.dumps(parts)}", max_out=3500 if final else None)
    emit("merge_done", final=final, reply=r); return r

def reduce_parts(parts, group_chars=15500, final_chars=10500):
    """Hierarchical reduce sized to the TPM budget: few, fat merge calls instead of many small ones."""
    while len(parts) > 1 and len(json.dumps(parts)) > final_chars:
        groups, cur = [], []
        for p in parts:
            if cur and len(json.dumps(cur + [p])) > group_chars: groups.append(cur); cur = []
            cur.append(p)
        groups.append(cur)
        if len(groups) == len(parts): groups = [parts[i:i + 2] for i in range(0, len(parts), 2)]  # guarantee progress
        emit("merge_start", parts_in=len(parts), calls=sum(1 for g in groups if len(g) > 1), final=False)
        parts = [_merge(g) if len(g) > 1 else g[0] for g in groups]
    emit("merge_start", parts_in=len(parts), calls=1, final=True)
    return _merge(parts, final=True)

def _norm(t): return re.sub(r"\s+", " ", t.lower().replace("’", "'").replace("‑", "-")).strip()

def verify_metrics(s, text):
    """full = quote found in transcript AND metric number inside the quote; number_only = number exists somewhere; no = neither."""
    import difflib
    nt = _norm(text); flat = nt.replace(",", "")
    for m in s.get("key_metrics", []):
        q = _norm(str(m.get("quote", "")))
        nums = re.findall(r"\d+(?:\.\d+)?", str(m.get("value", "")).replace(",", ""))
        in_quote = bool(nums) and all(n in q.replace(",", "") for n in nums)
        found = bool(q) and (q in nt or difflib.SequenceMatcher(None, nt, q, autojunk=False).find_longest_match(0, len(nt), 0, len(q)).size >= 0.85 * len(q))
        m["verified"] = "full" if (in_quote and found) else "number_only" if (nums and all(n in flat for n in nums)) else "no"
    return s

def summarize(text, meta):
    chunks = chunk(text)
    if not chunks: raise ValueError("empty transcript")
    emit("chunks_ready", total=len(chunks))
    parts = [map_chunk(c, i, len(chunks)) for i, c in enumerate(chunks)]
    final = reduce_parts(parts)
    final = {k: final.get(k, v) for k, v in SCHEMA.items()}
    final = verify_metrics(final, text)
    return {"company": meta["company"], "scrip_code": meta.get("scrip"), "nse_symbol": meta.get("symbol"), "quarter": meta.get("quarter"),
            "call_date": meta["date"], "filing_date": meta.get("filing_date"), "source": meta["source"], "source_url": meta["url"], "chunks_processed": len(chunks), **final}

ICON = {"full": "✅", "number_only": "🟡", True: "✅"}
def to_markdown(s):
    L = [f"# {s['company']} — {s.get('quarter') or 'Concall'} ({s['call_date']})", f"*Source: {s['source']} · {s['source_url']} · filed {s.get('filing_date')}*", "", "## TL;DR"]
    L += [f"- {x}" for x in s["tldr"]]
    for t, k in (("Management commentary", "management_commentary"), ("Guidance / outlook", "guidance"), ("Risks / concerns", "risks")):
        L += ["", f"## {t}"] + [f"- {x}" for x in s[k]]
    L += ["", "## Segment performance"] + [f"- **{x['segment']}**: {x['notes']}" for x in s["segment_performance"]]
    L += ["", "## Key numbers", "| Metric | Entity | Period | Value | Context | Verified |", "|---|---|---|---|---|---|"]
    L += [f"| {x['metric']} | {x.get('entity','')} | {x.get('period','')} | {x['value']} | {x.get('context','')} | {ICON.get(x.get('verified'), '⚠️')} |" for x in s["key_metrics"]]
    L += ["", "## Notable Q&A"] + [f"**Q ({x.get('asked_by','not stated')}):** {x['question']}\n\n**A (Answered by {x.get('answered_by') or 'Management'}):** {x['answer']}\n" for x in s["notable_qa"]]
    t = s.get("tone") or {}
    L += ["", f"## Management tone: {t.get('label','')}", t.get("reason", "")]
    return "\n".join(L)
