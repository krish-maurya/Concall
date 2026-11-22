import { useCallback, useEffect, useRef, useState } from "react";
import { fetchSummaries, fetchSummary, toListItem, wsUrl } from "../api";
import type { Summary, SummaryListItem } from "../types";
import { parseDate } from "../utils";

export type LiveState = "connecting" | "live" | "offline";

function sortItems(items: SummaryListItem[]): SummaryListItem[] {
  return [...items].sort((a, b) => {
    const da = parseDate(a.date)?.getTime() ?? 0;
    const db = parseDate(b.date)?.getTime() ?? 0;
    return db - da || b.id - a.id;
  });
}

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}

/** The list of summaries, kept live through the WebSocket. */
export function useSummaries() {
  const [items, setItems] = useState<SummaryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<LiveState>("connecting");
  const [fresh, setFresh] = useState<Set<number>>(new Set());

  const refresh = useCallback(async () => {
    try {
      setItems(sortItems(await fetchSummaries()));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let attempt = 0;
    let closed = false;

    const handle = (raw: unknown) => {
      let msg: unknown;
      try {
        msg = typeof raw === "string" ? JSON.parse(raw) : null;
      } catch {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      const m = msg as Record<string, unknown>;
      const candidate = (m.summary ?? m.data ?? m) as Record<string, unknown>;
      if (candidate && typeof candidate === "object" && "id" in candidate && "company" in candidate) {
        const item = toListItem(candidate);
        setItems((prev) => sortItems([item, ...prev.filter((i) => i.id !== item.id)]));
        setFresh((prev) => new Set(prev).add(item.id));
      }
    };

    const connect = () => {
      setLive("connecting");
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        if (attempt > 0) void refresh(); // catch anything missed while offline
        attempt = 0;
        setLive("live");
      };
      ws.onmessage = (ev) => handle(ev.data);
      ws.onerror = () => ws?.close();
      ws.onclose = () => {
        if (closed) return;
        setLive("offline");
        timer = window.setTimeout(connect, Math.min(15_000, 1_000 * 2 ** attempt++));
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, [refresh]);

  const markSeen = useCallback((id: number) => {
    setFresh((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  return { items, loading, error, live, fresh, refresh, markSeen };
}

/** One full summary, cached per id. */
export function useSummary(id: number | null) {
  const cache = useRef(new Map<number, Summary>());
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: number) => {
    const hit = cache.current.get(target);
    if (hit) {
      setData(hit);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const s = await fetchSummary(target);
      cache.current.set(target, s);
      setData(s);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (id === null) {
      setData(null);
      return;
    }
    let cancelled = false;
    const hit = cache.current.get(id);
    if (hit) {
      setData(hit);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    fetchSummary(id)
      .then((s) => {
        if (cancelled) return;
        cache.current.set(id, s);
        setData(s);
      })
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  const retry = useCallback(() => {
    if (id !== null) void load(id);
  }, [id, load]);

  return { data, loading, error, retry };
}
