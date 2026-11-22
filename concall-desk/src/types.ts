/** Row returned by GET /api/summaries */
export interface SummaryListItem {
  id: number;
  company: string;
  quarter: string;
  date: string | null;
  source: string | null;
}

/**
 * Full summary from GET /api/summaries/{id}.
 * The long-form sections can arrive as text, lists or objects, so they are
 * typed `unknown` and rendered by the generic <Rich /> component.
 */
export interface Summary {
  id: number;
  company: string;
  scrip_code?: string | number | null;
  nse_symbol?: string | null;
  quarter: string;
  call_date?: string | null;
  filing_date?: string | null;
  source?: string | null;
  source_url?: string | null;
  tldr?: unknown;
  management_commentary?: unknown;
  guidance?: unknown;
  segment_performance?: unknown;
  key_metrics?: unknown;
  notable_qa?: unknown;
  risks?: unknown;
  tone?: unknown;
}
