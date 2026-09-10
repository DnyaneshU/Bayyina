/**
 * The specimen page's only script: it renders the swatch grid from the tokens
 * themselves.
 *
 * Reading the computed values out of the stylesheet rather than repeating them
 * means the specimen cannot drift from the system it documents — a swatch chart
 * with hand-typed hexes is a chart that is wrong within a month.
 */
import "./index.css";

const GROUNDS = ["paper", "paper-raised"] as const;

const SWATCHES: Array<{ token: string; note: string }> = [
  { token: "ink-900", note: "headings, the answer" },
  { token: "ink-700", note: "body" },
  { token: "ink-500", note: "secondary — still AA" },
  { token: "edge", note: "a boundary you must find" },
  { token: "rule", note: "decorative hairline only" },
  { token: "danger", note: "genuine errors only, never an outcome" },
];

function luminance(hex: string): number {
  const channel = (offset: number) => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

function hex(token: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${token}`)
    .trim();
  if (value.startsWith("#")) return value;
  // Some browsers hand back rgb(); normalise so the ratio maths works.
  const parts = value.match(/\d+/g);
  return parts
    ? `#${parts
        .slice(0, 3)
        .map((n) => Number(n).toString(16).padStart(2, "0"))
        .join("")}`
    : "#000000";
}

const grid = document.querySelector<HTMLElement>("#swatches");
if (grid) {
  const ground = hex(GROUNDS[0]);
  grid.innerHTML = SWATCHES.map(({ token, note }) => {
    const value = hex(token);
    const ratio = contrast(value, ground);
    const meets =
      ratio >= 4.5 ? "AA text" : ratio >= 3 ? "AA non-text" : "decorative only";
    return `
      <div class="flex items-center gap-3 rounded border border-rule bg-paper-raised p-3">
        <span class="size-10 shrink-0 rounded border border-rule"
              style="background:${value}"></span>
        <span class="min-w-0">
          <span class="block text-sm font-semibold text-ink-900">--color-${token}</span>
          <span class="tabular block text-xs text-ink-500">${value} · ${ratio.toFixed(2)}:1 · ${meets}</span>
          <span class="block text-xs text-ink-500">${note}</span>
        </span>
      </div>`;
  }).join("");
}
