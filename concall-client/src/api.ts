import type { Summary, SummaryListItem } from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText || "Request failed"}`);
  return res;
}

export function toListItem(raw: Record<string, unknown>): SummaryListItem {
  return {
    id: Number(raw.id),
    company: String(raw.company ?? "Unknown company"),
    quarter: String(raw.quarter ?? ""),
    date: (raw.date ?? raw.call_date ?? null) as string | null,
    source: (raw.source ?? null) as string | null,
  };
}

/** GET /api/summaries */
export async function fetchSummaries(): Promise<SummaryListItem[]> {
  const data = await (await request("/api/summaries")).json();
  const rows: unknown[] = Array.isArray(data)
    ? data
    : Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data?.summaries)
        ? data.summaries
        : [];
  return rows.map((r) => toListItem(r as Record<string, unknown>));
}

/** GET /api/summaries/{id} */
export async function fetchSummary(id: number): Promise<Summary> {
  const raw = await (await request(`/api/summaries/${id}`)).json() as Record<string, unknown>;
  const nested = raw.json && typeof raw.json === "object" && !Array.isArray(raw.json)
    ? raw.json as Record<string, unknown>
    : null;
  return {
    ...raw,
    ...(nested ?? {}),
    id: Number(raw.id ?? nested?.id ?? id),
    company: String(nested?.company ?? raw.company ?? "Unknown company"),
    source_url: String(nested?.source_url ?? raw.source_url ?? raw.url ?? "") || null,
  } as Summary;
}

/** GET /api/summaries/{id}/md */
export async function fetchMarkdown(id: number): Promise<string> {
  return (await request(`/api/summaries/${id}/md`)).text();
}

/** POST /api/backfill?days=N */
export async function startBackfill(days: number): Promise<void> {
  await request(`/api/backfill?days=${days}`, { method: "POST" });
}

/** GET /api/progress */
export async function fetchProgress(): Promise<unknown[]> {
  const data = await (await request("/api/progress")).json();
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.events)) return data.events;
  if (Array.isArray(data?.progress)) return data.progress;
  return [];
}

/** WS /ws */
export function wsUrl(): string {
  if (BASE) return BASE.replace(/^http/, "ws") + "/ws";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

/**
 * WebSocket URLs for OTHER applications to subscribe to. Unlike wsUrl() (which may be the dev-server
 * proxy), this points at the backend itself: VITE_API_BASE, else VITE_API_TARGET, else this page's origin.
 */
export function backendWsUrls(): { summaries: string; live: string } {
  const target = (
    import.meta.env.VITE_API_BASE ||
    import.meta.env.VITE_API_TARGET ||
    "http://localhost:8000"
  ) as string;
  const base = target.replace(/\/$/, "").replace(/^http/, "ws");
  return { summaries: `${base}/ws`, live: `${base}/ws/live` };
}
