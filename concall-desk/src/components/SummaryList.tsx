import { useMemo, useState } from "react";
import type { LiveState } from "../hooks/useSummaries";
import type { SummaryListItem } from "../types";
import { groupLabel, hueFor, initials } from "../utils";

interface Props {
  items: SummaryListItem[];
  loading: boolean;
  error: string | null;
  live: LiveState;
  fresh: Set<number>;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRetry: () => void;
}

export function SummaryList({ items, loading, error, live, fresh, selectedId, onSelect, onRetry }: Props) {
  const [query, setQuery] = useState("");
  const [quarter, setQuarter] = useState("all");

  const quarters = useMemo(() => [...new Set(items.map((i) => i.quarter).filter(Boolean))], [items]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = items.filter(
      (i) => (quarter === "all" || i.quarter === quarter) && (!q || i.company.toLowerCase().includes(q)),
    );
    const map = new Map<string, SummaryListItem[]>();
    for (const item of filtered) {
      const label = groupLabel(item.date);
      map.set(label, [...(map.get(label) ?? []), item]);
    }
    return { total: filtered.length, entries: [...map.entries()] };
  }, [items, query, quarter]);

  return (
    <div className="list">
      <div className="list-tools">
        <label className="search">
          <span className="sr-only">Search by company name</span>
          <input
            type="search"
            placeholder="Search company"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {quarters.length > 1 && (
          <label className="select">
            <span className="sr-only">Filter by quarter</span>
            <select value={quarter} onChange={(e) => setQuarter(e.target.value)}>
              <option value="all">All quarters</option>
              {quarters.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="list-count" aria-live="polite">
        {loading ? "Loading calls…" : `${groups.total} ${groups.total === 1 ? "call" : "calls"}`}
        {live === "live" && <span className="list-live">Updating live</span>}
      </div>

      {error && (
        <div className="notice error" role="alert">
          <p>Couldn’t load the summaries ({error}). Check that the backend is running.</p>
          <button className="btn" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {loading && !error && (
        <div className="skeletons" aria-hidden="true">
          {Array.from({ length: 7 }).map((_, i) => (
            <div className="skeleton" key={i} />
          ))}
        </div>
      )}

      {!loading && !error && groups.total === 0 && (
        <div className="notice">
          <p>
            {items.length === 0
              ? "No concall summaries yet. Use “Fetch older calls” in the top bar to pull recent transcripts."
              : "No company matches that search."}
          </p>
        </div>
      )}

      {groups.entries.map(([label, rows]) => (
        <section className="group" key={label}>
          <h2 className="group-title">{label}</h2>
          <ul>
            {rows.map((item) => {
              const hue = hueFor(item.company);
              const isNew = fresh.has(item.id);
              return (
                <li key={item.id}>
                  <button
                    className={`row${item.id === selectedId ? " is-active" : ""}`}
                    onClick={() => onSelect(item.id)}
                    aria-current={item.id === selectedId ? "true" : undefined}
                  >
                    <span
                      className="avatar"
                      style={{ background: `hsl(${hue} 38% 90%)`, color: `hsl(${hue} 50% 26%)` }}
                      aria-hidden="true"
                    >
                      {initials(item.company)}
                    </span>
                    <span className="row-main">
                      <span className="row-company">{item.company}</span>
                      <span className="row-sub">
                        {item.quarter && <span className="chip">{item.quarter}</span>}
                        {item.source && <span className="row-source">{item.source}</span>}
                      </span>
                    </span>
                    {isNew && <span className="new-pill">New</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
