import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The audience is phone-first.
 *
 * A resident checking a rent increase is doing it on a phone, often a small and
 * old one, often not in their first language. Layout cannot be verified in
 * jsdom, so this checks the things that reliably break small screens and that a
 * source scan *can* catch — the same approach as rtl-safety.test.ts.
 */

const SRC = join(__dirname, "..");
const ROOT = join(SRC, "..");

function walk(dir: string, extensions: string[]): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full, extensions);
    return extensions.some((ext) => entry.endsWith(ext)) ? [full] : [];
  });
}

describe("phone safety", () => {
  it("declares the viewport", () => {
    const html = readFileSync(join(ROOT, "index.html"), "utf8");
    expect(html).toMatch(/name="viewport"[^>]*width=device-width/);
  });

  it("keeps the 44px tap-target floor", () => {
    // Below this, a person with imprecise touch cannot reliably hit a control.
    const css = readFileSync(join(SRC, "index.css"), "utf8");
    expect(css).toMatch(/min-block-size:\s*44px/);
  });

  it("uses no fixed pixel widths in components", () => {
    // A fixed width wider than ~320px forces the page to scroll sideways, which
    // is the single most common way a form becomes unusable on a phone.
    const offenders: string[] = [];
    for (const file of walk(SRC, [".tsx"])) {
      if (file.includes(".test.")) continue;
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, index) => {
          if (/\b(?:min-)?w-\[\d{3,}px\]/.test(line)) {
            offenders.push(`${relative(SRC, file)}:${index + 1} — ${line.trim()}`);
          }
        });
    }
    expect(offenders, `Fixed widths force sideways scrolling:\n  ${offenders.join("\n  ")}`).toEqual(
      [],
    );
  });

  it("breaks the rule signature so it cannot overflow", () => {
    // A sha256 signature is 71 unbroken characters. Without an explicit break it
    // widens the page past the viewport on every phone.
    const checker = readFileSync(join(SRC, "components", "Checker.tsx"), "utf8");
    const signatureLine = checker
      .split("\n")
      .find((line) => line.includes("rule_signature") && line.includes("slice"));

    expect(signatureLine, "the signature is no longer rendered here").toBeDefined();
    expect(checker).toMatch(/break-all/);
  });
});
