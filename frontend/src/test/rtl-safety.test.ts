import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * RTL is a layout concern, not a font swap.
 *
 * The App test asserts that switching to Arabic sets dir="rtl". That is
 * necessary but not sufficient: a component written with `ml-4` instead of
 * `ms-4` passes that test and still fails to mirror. RTL regressions are silent
 * — nothing throws, the layout is simply wrong, and nobody notices until a demo
 * in front of a judging panel.
 *
 * So the rule is enforced here rather than remembered: physical direction
 * properties are banned, logical ones are required.
 */

const SRC = join(__dirname, "..");

/** Tailwind utilities that hard-code a side, and their logical equivalents. */
const BANNED_CLASSES: Array<[RegExp, string]> = [
  [/\bml-(\d|\[|auto)/, "ms-* (margin-inline-start)"],
  [/\bmr-(\d|\[|auto)/, "me-* (margin-inline-end)"],
  [/\bpl-(\d|\[)/, "ps-* (padding-inline-start)"],
  [/\bpr-(\d|\[)/, "pe-* (padding-inline-end)"],
  [/\btext-left\b/, "text-start"],
  [/\btext-right\b/, "text-end"],
  [/\bborder-l\b|\bborder-l-/, "border-s-*"],
  [/\bborder-r\b|\bborder-r-/, "border-e-*"],
  [/\brounded-l\b|\brounded-l-/, "rounded-s-*"],
  [/\brounded-r\b|\brounded-r-/, "rounded-e-*"],
  [/\bleft-(\d|\[)/, "start-*"],
  [/\bright-(\d|\[)/, "end-*"],
];

/** Raw CSS properties that hard-code a side. */
const BANNED_CSS: Array<[RegExp, string]> = [
  [/margin-left\s*:/, "margin-inline-start"],
  [/margin-right\s*:/, "margin-inline-end"],
  [/padding-left\s*:/, "padding-inline-start"],
  [/padding-right\s*:/, "padding-inline-end"],
  [/border-left\s*:/, "border-inline-start"],
  [/border-right\s*:/, "border-inline-end"],
  [/text-align\s*:\s*(left|right)/, "text-align: start | end"],
];

function walk(dir: string, extensions: string[]): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full, extensions);
    return extensions.some((ext) => entry.endsWith(ext)) ? [full] : [];
  });
}

function violations(files: string[], rules: Array<[RegExp, string]>): string[] {
  const found: string[] = [];
  for (const file of files) {
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, index) => {
      // A file may opt out on a single line with an explicit justification.
      if (line.includes("rtl-safe-ignore")) return;
      for (const [pattern, replacement] of rules) {
        if (pattern.test(line)) {
          found.push(
            `${relative(SRC, file)}:${index + 1} — "${line.trim()}"\n` +
              `      use ${replacement} instead`,
          );
        }
      }
    });
  }
  return found;
}

describe("RTL safety", () => {
  it("uses no physical direction utilities in components", () => {
    const files = walk(SRC, [".tsx", ".ts"]).filter((f) => !f.includes("rtl-safety"));
    const found = violations(files, BANNED_CLASSES);
    expect(found, `Physical direction utilities break Arabic:\n  ${found.join("\n  ")}`).toEqual(
      [],
    );
  });

  it("uses no physical direction properties in stylesheets", () => {
    const found = violations(walk(SRC, [".css"]), BANNED_CSS);
    expect(found, `Physical CSS properties break Arabic:\n  ${found.join("\n  ")}`).toEqual([]);
  });
});
