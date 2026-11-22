import { shorten, toneKind, toneLabel } from "../utils";

export function ToneBadge({ tone }: { tone: unknown }) {
  const label = toneLabel(tone);
  if (!label) return null;
  return (
    <span className={`tone tone-${toneKind(label)}`} title={label}>
      <span className="tone-dot" aria-hidden="true" />
      {shorten(label)}
    </span>
  );
}
