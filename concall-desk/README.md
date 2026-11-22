# Concall Desk

React + TypeScript (Vite) frontend for the earnings-call summaries API. Uses npm.

## Run

```bash
npm install
cp .env.example .env     # set VITE_API_TARGET to your backend (default http://localhost:8000)
npm run dev              # http://localhost:5173
```

In dev, Vite proxies `/api` and `/ws` to `VITE_API_TARGET`, so there are no CORS issues.

## Build

```bash
npm run build            # output in dist/
npm run preview
```

If the backend is on a different origin in production, set `VITE_API_BASE=https://your-backend` before building.

## How it maps to the API

| Route | Used for |
| --- | --- |
| `GET /api/summaries` | Left list, grouped by date, newest first, searchable by company |
| `GET /api/summaries/{id}` | Detail view when a company is selected |
| `GET /api/summaries/{id}/md` | "Copy as Markdown" and "Download .md" buttons |
| `POST /api/backfill?days=N` | "Fetch older calls" drawer |
| `GET /api/progress` | Activity list in the same drawer (polled every 3 s while open) |
| `WS /ws` | New summaries appear at the top with a "New" tag; auto-reconnects |

## Structure

```
src/
  api.ts                  fetch + WebSocket helpers
  types.ts                Summary types
  hooks/useSummaries.ts   list + live updates, single-summary cache
  components/
    SummaryList.tsx       company list, search, quarter filter
    SummaryDetail.tsx     header, TL;DR, sections
    Rich.tsx              renders text / lists / objects, metric tiles, Q&A accordion
    ProgressPanel.tsx     backfill + activity drawer
    ToneBadge.tsx
  styles.css
```

The long sections (guidance, key metrics, segments, Q&A, risks) are rendered by shape-tolerant
components, so they work whether the backend returns text, arrays or objects.
