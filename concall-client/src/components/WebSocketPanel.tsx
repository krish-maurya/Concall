import { useEffect, useRef, useState } from "react";
import { backendWsUrls, fetchSummaries, fetchSummary } from "../api";

interface Props {
  onClose: () => void;
}

type Sample = { state: "idle" | "loading" | "ready" | "empty" | "failed"; json: string };
type Test = "idle" | "testing" | "ok" | "failed";

export function WebSocketPanel({ onClose }: Props) {
  const urls = backendWsUrls();
  const [copied, setCopied] = useState<string | null>(null);
  const [sample, setSample] = useState<Sample>({ state: "idle", json: "" });
  const [test, setTest] = useState<Test>("idle");
  const closeRef = useRef<HTMLButtonElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      socketRef.current?.close();
    };
  }, [onClose]);

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
    } catch {
      setCopied(null);
    }
  };

  /** "Fetch one": load the newest stored summary - the same structure every WebSocket client receives. */
  const fetchOne = async () => {
    setSample({ state: "loading", json: "" });
    try {
      const list = await fetchSummaries();
      if (list.length === 0) {
        setSample({ state: "empty", json: "" });
        return;
      }
      const newest = list.reduce((a, b) => (b.id > a.id ? b : a));
      setSample({ state: "ready", json: JSON.stringify(await fetchSummary(newest.id), null, 2) });
    } catch {
      setSample({ state: "failed", json: "" });
    }
  };

  const testConnection = () => {
    socketRef.current?.close();
    setTest("testing");
    let settled = false;
    const finish = (result: Test) => {
      if (settled) return;
      settled = true;
      setTest(result);
      window.clearTimeout(timer);
    };
    const timer = window.setTimeout(() => {
      finish("failed");
      socketRef.current?.close();
    }, 4000);
    try {
      const ws = new WebSocket(urls.summaries);
      socketRef.current = ws;
      ws.onopen = () => {
        finish("ok");
        ws.close();
      };
      ws.onerror = () => finish("failed");
    } catch {
      finish("failed");
    }
  };

  const jsSnippet = `const ws = new WebSocket("${urls.summaries}");
ws.onmessage = (e) => {
  const summary = JSON.parse(e.data);
  console.log(summary.company, summary.quarter, summary.tldr);
};
ws.onclose = () => setTimeout(() => location.reload(), 2000); // reconnect`;

  const pySnippet = `import asyncio, json, websockets

async def listen():
    async with websockets.connect("${urls.summaries}") as ws:
        async for msg in ws:
            s = json.loads(msg)
            print("NEW:", s["company"], s["quarter"])

asyncio.run(listen())`;

  const urlRow = (key: string, label: string, url: string, hint: string) => (
    <div>
      <span className="field-label">{label}</span>
      <div className="url-row">
        <input readOnly value={url} aria-label={label} onFocus={(e) => e.currentTarget.select()} />
        <button className="btn" onClick={() => copy(key, url)}>
          {copied === key ? "Copied" : "Copy"}
        </button>
      </div>
      <p className="muted small">{hint}</p>
    </div>
  );

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="WebSocket feed" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2>WebSocket feed</h2>
          <button ref={closeRef} className="btn ghost" onClick={onClose}>
            Close
          </button>
        </header>

        <div className="drawer-body">
          <p className="muted">Any app can connect to these addresses and receive each new summary the moment it is ready. No login is needed.</p>

          {urlRow("summaries", "Summaries feed", urls.summaries, "Sends one JSON message per finished summary. Only summaries finished after you connect are sent.")}
          {urlRow("live", "Pipeline activity feed", urls.live, "Optional. Every pipeline step and raw LLM reply, with the recent history replayed on connect.")}

          <div className="backfill">
            <button className="btn primary" onClick={testConnection} disabled={test === "testing"}>
              {test === "testing" ? "Testing…" : "Test connection"}
            </button>
            {test === "ok" && <span className="notice ok">Connected. The feed is reachable.</span>}
            {test === "failed" && <span className="notice error">Couldn’t connect. Check the backend is running.</span>}
          </div>

          <h3>Fetch one example</h3>
          <p className="muted">Loads the newest stored summary. WebSocket messages have this same structure.</p>
          <div className="backfill">
            <button className="btn" onClick={fetchOne} disabled={sample.state === "loading"}>
              {sample.state === "loading" ? "Fetching…" : "Fetch one"}
            </button>
            {sample.state === "ready" && (
              <button className="btn" onClick={() => copy("sample", sample.json)}>
                {copied === "sample" ? "Copied" : "Copy JSON"}
              </button>
            )}
          </div>
          {sample.state === "empty" && <p className="notice">No summaries yet. One will appear here once the first transcript is processed.</p>}
          {sample.state === "failed" && <p className="notice error">Couldn’t load a summary. Check the backend and try again.</p>}
          {sample.state === "ready" && <pre className="code code-json">{sample.json}</pre>}

          <h3>Connect from JavaScript</h3>
          <pre className="code code-snippet">{jsSnippet}</pre>
          <h3>Connect from Python</h3>
          <pre className="code code-snippet">{pySnippet}</pre>
          <p className="muted small">Python needs <code>pip install websockets</code>.</p>
        </div>
      </aside>
    </div>
  );
}
