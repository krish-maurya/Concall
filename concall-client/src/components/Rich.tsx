import type { ReactElement } from "react";
import { humanize, isEmpty, isPrimitive, pickKey } from "../utils";

const TITLE_KEYS = [
  "title", "name", "segment", "metric", "label", "topic", "risk", "heading",
  "item", "parameter", "area", "category", "theme",
];
// Keys whose value reads as body text, so the label would only add noise.
const BODY_KEYS = new Set([
  "description", "detail", "details", "commentary", "text", "summary", "comment",
  "note", "notes", "content", "performance", "outlook", "insight",
]);
const VALUE_KEYS = ["value", "current", "actual", "amount", "figure", "number", "result"];

type Obj = Record<string, unknown>;

function Text({ text }: { text: string }): ReactElement {
  const lines = text.split(/\n+/).map((l) => l.trim()).filter(Boolean);
  const bullet = /^[-•*–]\s+/;
  if (lines.length > 1 && lines.every((l) => bullet.test(l))) {
    return (
      <ul className="bullets">
        {lines.map((l, i) => (
          <li key={i}>{l.replace(bullet, "")}</li>
        ))}
      </ul>
    );
  }
  return (
    <>
      {lines.map((l, i) => (
        <p key={i}>{l.replace(bullet, "")}</p>
      ))}
    </>
  );
}

function ItemCard({ obj }: { obj: Obj }): ReactElement {
  const titleKey = pickKey(obj, TITLE_KEYS);
  const rest = Object.entries(obj).filter(([k, v]) => k !== titleKey && !isEmpty(v));
  return (
    <div className="item">
      {titleKey && <h4>{String(obj[titleKey])}</h4>}
      {rest.map(([k, v]) =>
        isPrimitive(v) ? (
          BODY_KEYS.has(k.toLowerCase()) ? (
            <Text key={k} text={String(v)} />
          ) : (
            <p key={k} className="kv">
              <span className="k">{humanize(k)}</span>
              <span>{String(v)}</span>
            </p>
          )
        ) : (
          <div key={k} className="kv-block">
            <span className="k">{humanize(k)}</span>
            <Rich value={v} />
          </div>
        ),
      )}
    </div>
  );
}

/** Renders text, lists, objects or nested combinations without knowing the exact shape. */
export function Rich({ value, grid = false }: { value: unknown; grid?: boolean }): ReactElement | null {
  if (isEmpty(value)) return null;
  if (isPrimitive(value)) return <Text text={String(value)} />;

  if (Array.isArray(value)) {
    const rows = value.filter((v) => !isEmpty(v));
    if (rows.every(isPrimitive)) {
      return (
        <ul className="bullets">
          {rows.map((v, i) => (
            <li key={i}>{String(v)}</li>
          ))}
        </ul>
      );
    }
    return (
      <div className={grid ? "stack grid-2" : "stack"}>
        {rows.map((v, i) => (
          <Rich key={i} value={v} />
        ))}
      </div>
    );
  }
  return <ItemCard obj={value as Obj} />;
}

/* ---------- Key metrics ---------- */

interface Tile {
  label: string;
  value: string | null;
  rest: Obj;
}

function toTiles(value: unknown): Tile[] | null {
  if (Array.isArray(value)) {
    const rows = value.filter((v) => !isEmpty(v));
    if (!rows.every((v) => v && typeof v === "object" && !Array.isArray(v))) return null;
    return (rows as Obj[]).map((o, i) => {
      const labelKey = pickKey(o, TITLE_KEYS);
      const valueKey = pickKey(o, VALUE_KEYS);
      const rest: Obj = {};
      for (const [k, v] of Object.entries(o)) if (k !== labelKey && k !== valueKey && !isEmpty(v)) rest[k] = v;
      return {
        label: labelKey ? String(o[labelKey]) : `Metric ${i + 1}`,
        value: valueKey ? String(o[valueKey]) : null,
        rest,
      };
    });
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Obj)
      .filter(([, v]) => !isEmpty(v))
      .map(([k, v]) => {
        if (isPrimitive(v)) return { label: humanize(k), value: String(v), rest: {} };
        if (v && typeof v === "object" && !Array.isArray(v)) {
          const o = v as Obj;
          const valueKey = pickKey(o, VALUE_KEYS);
          const rest: Obj = {};
          for (const [kk, vv] of Object.entries(o)) if (kk !== valueKey && !isEmpty(vv)) rest[kk] = vv;
          return { label: humanize(k), value: valueKey ? String(o[valueKey]) : null, rest };
        }
        return { label: humanize(k), value: null, rest: { [k]: v } };
      });
  }
  return null;
}

export function MetricGrid({ value }: { value: unknown }): ReactElement | null {
  if (isEmpty(value)) return null;
  const tiles = toTiles(value);
  if (!tiles) return <Rich value={value} />;
  return (
    <div className="metrics">
      {tiles.map((t, i) => (
        <div className="metric" key={i}>
          <span className="metric-label">{t.label}</span>
          {t.value && <span className="metric-value">{t.value}</span>}
          {Object.entries(t.rest).map(([k, v]) =>
            isPrimitive(v) ? (
              <span className="metric-note" key={k}>
                {humanize(k)}: {String(v)}
              </span>
            ) : (
              <div className="metric-note" key={k}>
                <Rich value={v} />
              </div>
            ),
          )}
        </div>
      ))}
    </div>
  );
}

/* ---------- Notable Q&A ---------- */

const Q_KEYS = ["question", "q", "analyst_question", "ask"];
const A_KEYS = ["answer", "a", "management_response", "response", "reply"];

export function QAList({ value }: { value: unknown }): ReactElement | null {
  if (isEmpty(value)) return null;
  const rows = Array.isArray(value) ? value.filter((v) => !isEmpty(v)) : null;
  const ok = rows && rows.every((r) => r && typeof r === "object" && !Array.isArray(r) && pickKey(r as Obj, Q_KEYS));
  if (!rows || !ok) return <Rich value={value} />;

  return (
    <div className="qa-list">
      {(rows as Obj[]).map((r, i) => {
        const qk = pickKey(r, Q_KEYS)!;
        const ak = pickKey(r, A_KEYS);
        const askedByKey = pickKey(r, ["asked_by", "askedby", "analyst", "speaker", "question_by"]);
        const answeredByKey = pickKey(r, ["answered_by", "answeredby", "responded_by", "responder", "management"]);
        const meta = Object.entries(r).filter(([k, v]) =>
          k !== qk &&
          k !== ak &&
          k !== askedByKey &&
          k !== answeredByKey &&
          isPrimitive(v) &&
          !isEmpty(v),
        );
        return (
          <details className="qa" key={i} open={i === 0}>
            <summary>
              <span className="qa-q">{String(r[qk])}</span>
              <span className="qa-meta">
                {askedByKey ? `Asked by: ${String(r[askedByKey])}` : null}
                {meta.length > 0 && `${askedByKey ? " · " : ""}${meta.map(([k, v]) => `${humanize(k)}: ${String(v)}`).join(" · ")}`}
              </span>
            </summary>
            <div className="qa-a">
              {answeredByKey ? (
                <span className="qa-answer-by">Answered by: {String(r[answeredByKey])}</span>
              ) : (
                <span className="qa-answer-by">Answered by: Management</span>
              )}
              {ak ? <Rich value={r[ak]} /> : <p className="muted">No answer recorded.</p>}
            </div>
          </details>
        );
      })}
    </div>
  );
}
