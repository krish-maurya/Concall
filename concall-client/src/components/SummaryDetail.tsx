import { useState } from "react";
import { fetchMarkdown } from "../api";
import type { Summary } from "../types";
import { formatDate, hueFor, initials, isEmpty, toneLabel } from "../utils";
import { MetricGrid, QAList, Rich } from "./Rich";
import { ToneBadge } from "./ToneBadge";

interface Props {
  data: Summary | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onBack: () => void;
}

interface Section {
  key: string;
  label: string;
  value: unknown;
  render: (v: unknown) => JSX.Element | null;
}

function sectionsOf(s: Summary): Section[] {
  const list: Section[] = [
    { key: "metrics", label: "Key metrics", value: s.key_metrics, render: (v) => <MetricGrid value={v} /> },
    { key: "guidance", label: "Guidance", value: s.guidance, render: (v) => <Rich value={v} /> },
    { key: "segments", label: "Segment performance", value: s.segment_performance, render: (v) => <Rich value={v} grid /> },
    { key: "commentary", label: "Management commentary", value: s.management_commentary, render: (v) => <Rich value={v} /> },
    { key: "qa", label: "Notable Q&A", value: s.notable_qa, render: (v) => <QAList value={v} /> },
    { key: "risks", label: "Risks", value: s.risks, render: (v) => <Rich value={v} /> },
  ];
  const tone = toneLabel(s.tone);
  // Only show a tone section when there is more to read than the badge already says.
  if (!isEmpty(s.tone) && (typeof s.tone !== "string" || (tone && tone.length > 28))) {
    list.push({ key: "tone", label: "Tone of the call", value: s.tone, render: (v) => <Rich value={v} /> });
  }
  return list.filter((x) => !isEmpty(x.value));
}

export function SummaryDetail({ data, loading, error, onRetry, onBack }: Props) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");

  if (loading) {
    return (
      <div className="detail-inner" aria-busy="true">
        <button className="back" onClick={onBack}>Back to all calls</button>
        <div className="skeleton tall" />
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="detail-inner">
        <button className="back" onClick={onBack}>Back to all calls</button>
        <div className="notice error" role="alert">
          <p>Couldn’t load this summary ({error}).</p>
          <button className="btn" onClick={onRetry}>Try again</button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-detail">
        <p>Select a company on the left to read its latest concall summary.</p>
      </div>
    );
  }

  const hue = hueFor(data.company);
  const sections = sectionsOf(data);
  const hasTldr = !isEmpty(data.tldr);

  const goTo = (key: string) =>
    document.getElementById(`sec-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

  const copyMd = async () => {
    try {
      await navigator.clipboard.writeText(await fetchMarkdown(data.id));
      setCopied("done");
    } catch {
      setCopied("failed");
    }
    window.setTimeout(() => setCopied("idle"), 2200);
  };

  const downloadMd = async () => {
    try {
      const text = await fetchMarkdown(data.id);
      const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.company}-${data.quarter}.md`.replace(/[^\w.-]+/g, "_");
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setCopied("failed");
      window.setTimeout(() => setCopied("idle"), 2200);
    }
  };

  const ids = [
    data.nse_symbol ? { k: "NSE", v: data.nse_symbol } : null,
    data.scrip_code ? { k: "BSE", v: String(data.scrip_code) } : null,
  ].filter((x): x is { k: string; v: string } => x !== null);

  return (
    <article className="detail-inner">
      <button className="back" onClick={onBack}>Back to all calls</button>

      <header className="d-head">
        <div className="d-title-row">
          <span
            className="avatar lg"
            style={{ background: `hsl(${hue} 38% 90%)`, color: `hsl(${hue} 50% 26%)` }}
            aria-hidden="true"
          >
            {initials(data.company)}
          </span>
          <div>
            <h1>{data.company}</h1>
            <div className="d-ids">
              {data.quarter && <span className="chip strong">{data.quarter}</span>}
              {ids.map((i) => (
                <span className="chip" key={i.k}>{i.k} {i.v}</span>
              ))}
              <ToneBadge tone={data.tone} />
            </div>
          </div>
        </div>

        <dl className="d-dates">
          <div>
            <dt>Call date</dt>
            <dd>{formatDate(data.call_date)}</dd>
          </div>
          <div>
            <dt>Filed on</dt>
            <dd>{formatDate(data.filing_date)}</dd>
          </div>
          {data.source && (
            <div>
              <dt>Source</dt>
              <dd>
                {data.source_url ? (
                  <a href={data.source_url} target="_blank" rel="noreferrer">{data.source}</a>
                ) : (
                  data.source
                )}
              </dd>
            </div>
          )}
        </dl>

        <div className="d-actions">
          <button className="btn" onClick={copyMd}>
            {copied === "done" ? "Copied" : copied === "failed" ? "Couldn’t copy" : "Copy as Markdown"}
          </button>
          <button className="btn" onClick={downloadMd}>Download .md</button>
          {data.source_url && (
            <a className="btn" href={data.source_url} target="_blank" rel="noreferrer">Open original</a>
          )}
        </div>
      </header>

      {hasTldr && (
        <section className="lede" aria-label="In short">
          <div className="lede-text"><Rich value={data.tldr} /></div>
        </section>
      )}

      {sections.length > 1 && (
        <nav className="jump" aria-label="Sections">
          {sections.map((s) => (
            <button key={s.key} onClick={() => goTo(s.key)}>{s.label}</button>
          ))}
        </nav>
      )}

      {sections.map((s) => (
        <section className={`sec sec-${s.key}`} id={`sec-${s.key}`} key={s.key}>
          <h2>{s.label}</h2>
          {s.render(s.value)}
        </section>
      ))}

      {!hasTldr && sections.length === 0 && (
        <div className="notice"><p>This summary has no content yet.</p></div>
      )}
    </article>
  );
}
