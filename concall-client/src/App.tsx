import { useCallback, useEffect, useState } from "react";
import { ProgressPanel } from "./components/ProgressPanel";
import { SummaryDetail } from "./components/SummaryDetail";
import { SummaryList } from "./components/SummaryList";
import { WebSocketPanel } from "./components/WebSocketPanel";
import { useSummaries, useSummary } from "./hooks/useSummaries";

function readHash(): number | null {
  const m = window.location.hash.match(/^#\/s\/(\d+)/);
  return m ? Number(m[1]) : null;
}

export default function App() {
  const { items, loading, error, live, fresh, refresh, markSeen } = useSummaries();
  const [selectedId, setSelectedId] = useState<number | null>(readHash);
  const [panelOpen, setPanelOpen] = useState(false);
  const [wsOpen, setWsOpen] = useState(false);
  const detail = useSummary(selectedId);

  useEffect(() => {
    const onHash = () => setSelectedId(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // On wide screens open the newest call straight away so the page is never empty.
  useEffect(() => {
    if (selectedId === null && items.length > 0 && window.matchMedia("(min-width: 900px)").matches) {
      window.location.hash = `#/s/${items[0].id}`;
    }
  }, [selectedId, items]);

  const select = useCallback(
    (id: number) => {
      markSeen(id);
      window.location.hash = `#/s/${id}`;
    },
    [markSeen],
  );

  const back = useCallback(() => {
    history.pushState(null, "", window.location.pathname + window.location.search);
    setSelectedId(null);
  }, []);

  const liveText = live === "live" ? "Live" : live === "connecting" ? "Connecting…" : "Offline, retrying";

  return (
    <div className={`app${selectedId !== null ? " has-selection" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <h1 className="brand-name">Concall Desk</h1>
            <p className="brand-sub">Latest earnings call summaries</p>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`live live-${live}`} role="status">
            <span className="live-dot" aria-hidden="true" />
            {liveText}
          </span>
          <button className="btn" onClick={() => setWsOpen(true)}>WebSocket</button>
          <button className="btn" onClick={() => setPanelOpen(true)}>Fetch older calls</button>
        </div>
      </header>

      <main className="workspace">
        <aside className="list-pane" aria-label="Concall list">
          <SummaryList
            items={items}
            loading={loading}
            error={error}
            live={live}
            fresh={fresh}
            selectedId={selectedId}
            onSelect={select}
            onRetry={refresh}
          />
        </aside>
        <section className="detail-pane" aria-label="Summary">
          <SummaryDetail data={detail.data} loading={detail.loading} error={detail.error} onRetry={detail.retry} onBack={back} />
        </section>
      </main>

      {panelOpen && <ProgressPanel onClose={() => setPanelOpen(false)} onActivity={refresh} />}
      {wsOpen && <WebSocketPanel onClose={() => setWsOpen(false)} />}
    </div>
  );
}
