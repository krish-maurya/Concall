import { useEffect, useRef, useState } from "react";
import { fetchProgress, startBackfill } from "../api";
import { isPrimitive, pickKey } from "../utils";

interface Props {
  onClose: () => void;
  onActivity: () => void;
}

interface Line {
  time: string | null;
  text: string;
}

function toLine(e: unknown): Line {
  if (isPrimitive(e)) return { time: null, text: String(e) };
  if (e && typeof e === "object") {
    const o = e as Record<string, unknown>;
    const tk = pickKey(o, ["time", "ts", "timestamp", "at", "created_at"]);
    const mk = pickKey(o, ["message", "msg", "event", "text", "status", "detail"]);
    let time: string | null = null;
    if (tk) {
      const d = new Date(typeof o[tk] === "number" && (o[tk] as number) < 1e12 ? (o[tk] as number) * 1000 : (o[tk] as string | number));
      time = Number.isNaN(d.getTime()) ? String(o[tk]) : d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    const rest = Object.entries(o)
      .filter(([k, v]) => k !== tk && k !== mk && isPrimitive(v))
      .map(([k, v]) => `${k}: ${String(v)}`)
      .join(", ");
    const main = mk ? String(o[mk]) : "";
    return { time, text: [main, rest].filter(Boolean).join(" — ") || JSON.stringify(o) };
  }
  return { time: null, text: String(e) };
}

export function ProgressPanel({ onClose, onActivity }: Props) {
  const [days, setDays] = useState(45);
  const [events, setEvents] = useState<Line[]>([]);
  const [status, setStatus] = useState<"idle" | "starting" | "started" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  const lastSig = useRef("");
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const raw = await fetchProgress();
        if (stop) return;
        const sig = JSON.stringify(raw.slice(-3));
        if (sig !== lastSig.current) {
          if (lastSig.current) onActivity();
          lastSig.current = sig;
        }
        setEvents(raw.map(toLine).reverse());
        setError(null);
      } catch (e) {
        if (!stop) setError(e instanceof Error ? e.message : "Failed to load progress");
      }
    };
    void tick();
    const id = window.setInterval(tick, 3000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [onActivity]);

  const run = async () => {
    setStatus("starting");
    try {
      await startBackfill(days);
      setStatus("started");
    } catch {
      setStatus("failed");
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Fetch older calls" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2>Fetch older calls</h2>
          <button ref={closeRef} className="btn ghost" onClick={onClose}>
            Close
          </button>
        </header>

        <div className="drawer-body">
          <p className="muted">Pull transcripts from the past few weeks. New summaries appear in the list as they finish.</p>
          <div className="backfill">
            <label>
              <span>Days to go back</span>
              <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))} />
            </label>
            <button className="btn primary" onClick={run} disabled={status === "starting"}>
              {status === "starting" ? "Starting…" : "Start fetching"}
            </button>
          </div>
          {status === "started" && <p className="notice ok">Started. Progress shows below.</p>}
          {status === "failed" && <p className="notice error">Couldn’t start the fetch. Check the backend and try again.</p>}

          <h3>Recent activity</h3>
          {error && <p className="notice error">Couldn’t load activity ({error}).</p>}
          {!error && events.length === 0 && <p className="muted">Nothing running right now.</p>}
          <ol className="events">
            {events.map((e, i) => (
              <li key={i}>
                {e.time && <time>{e.time}</time>}
                <span>{e.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  );
}
