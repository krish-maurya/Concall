export type Primitive = string | number | boolean;

export function isPrimitive(v: unknown): v is Primitive {
  return typeof v === "string" || typeof v === "number" || typeof v === "boolean";
}

export function isEmpty(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.every(isEmpty);
  if (typeof v === "object") return Object.values(v as object).every(isEmpty);
  return false;
}

export function humanize(key: string): string {
  const s = key.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** First key from `keys` (case-insensitive) that holds a primitive value. */
export function pickKey(obj: Record<string, unknown>, keys: string[]): string | null {
  const lower = new Map(Object.keys(obj).map((k) => [k.toLowerCase(), k]));
  for (const k of keys) {
    const real = lower.get(k);
    if (real && isPrimitive(obj[real]) && String(obj[real]).trim() !== "") return real;
  }
  return null;
}

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

export function formatDate(value: string | null | undefined): string {
  const d = parseDate(value);
  return d ? dateFmt.format(d) : "Date not available";
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function groupLabel(value: string | null | undefined): string {
  const d = parseDate(value);
  if (!d) return "Undated";
  const diff = Math.round((startOfDay(new Date()) - startOfDay(d)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return dateFmt.format(d);
}

export function initials(name: string): string {
  const words = name
    .replace(/\b(limited|ltd\.?|inc\.?|corporation|corp\.?|the|of|and|&)\b/gi, "")
    .split(/[\s.\-_/]+/)
    .filter(Boolean);
  const src = words.length ? words : name.split(/\s+/);
  return (src[0]?.[0] ?? "?").concat(src[1]?.[0] ?? "").toUpperCase();
}

export function hueFor(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

/** Short label for the tone of the call, whatever shape the backend sends. */
export function toneLabel(tone: unknown): string | null {
  if (isEmpty(tone)) return null;
  if (isPrimitive(tone)) return String(tone);
  if (Array.isArray(tone)) return tone.find(isPrimitive) !== undefined ? String(tone.find(isPrimitive)) : null;
  const obj = tone as Record<string, unknown>;
  const k = pickKey(obj, ["tone", "label", "sentiment", "overall", "summary", "description"]);
  if (k) return String(obj[k]);
  const first = Object.values(obj).find(isPrimitive);
  return first === undefined ? null : String(first);
}

export type ToneKind = "positive" | "cautious" | "negative" | "neutral";

export function toneKind(label: string | null): ToneKind {
  if (!label) return "neutral";
  const t = label.toLowerCase();
  if (/(negative|bearish|concern|pessimis|weak|worr|defensive|subdued|challeng)/.test(t)) return "negative";
  if (/(positive|optimis|bullish|confiden|upbeat|strong|bullish|buoyant|constructive)/.test(t)) return "positive";
  if (/(cautio|mixed|measured|balanced|guarded|neutral|prudent)/.test(t)) return "cautious";
  return "neutral";
}

export function shorten(text: string, max = 28): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 12 ? cut.slice(0, lastSpace) : cut).replace(/[,;:.\-]+$/, "") + "…";
}
