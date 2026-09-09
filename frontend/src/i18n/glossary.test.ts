import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import en from "./locales/en.json";

/**
 * docs/GLOSSARY.md says it "gates all user-visible copy". Until this file, it
 * gated nothing — it was a document people were expected to remember.
 *
 * Two things are checked. The standing disclosures must match the glossary
 * character for character, because they are the compliance surface and a
 * paraphrase is not the kind of thing anyone notices by reading. And the banned
 * vocabulary must not appear, because each banned word either claims legal
 * authority, predicts an outcome, or turns information into advice.
 */

const GLOSSARY = join(__dirname, "..", "..", "..", "docs", "GLOSSARY.md");

/**
 * Key in en.json → the exact text the glossary specifies for the web.
 * Where the glossary records a surface variant, that variant is the one here.
 */
const DISCLOSURES: Array<[string, string]> = [
  ["disclosure.notAdvice", "Information from Dubai's published rental rules, not legal advice."],
  [
    "disclosure.provisional",
    "Our encoding of these rules is pending review by a qualified lawyer, so treat this as information to check, not a ruling.",
  ],
  [
    "disclosure.notOfficial",
    "This is not an official determination. Bayyina is not a government entity and does not act for any authority.",
  ],
  ["disclosure.callerStated", "As stated by you. Not independently verified."],
  [
    "disclosure.dataSource",
    "Based on registered tenancy contracts published as open data by Dubai Land Department.",
  ],
];

/**
 * Banned everywhere (docs/GLOSSARY.md §1). The test is: if a sentence would be
 * improper coming from a non-lawyer, we do not say it.
 */
const BANNED = [
  "advice",
  "advise",
  "recommend",
  "you should",
  "your rights",
  "we determine",
  "guarantee",
  "win",
  "case is strong",
  "ruling",
  "judgement",
  "judgment",
  "fair rent",
  "legal rent",
];

/**
 * The only keys allowed to contain a banned word, because they *negate* it.
 * "not legal advice" is the disclosure; "advice" alone is the thing we refuse
 * to give. Adding a key here should feel uncomfortable.
 */
const NEGATED: Record<string, string[]> = {
  "disclosure.notAdvice": ["advice"],
  "disclosure.provisional": ["ruling"],
};

function leaves(value: unknown, prefix = ""): Array<[string, string]> {
  if (typeof value !== "object" || value === null) return [[prefix, String(value)]];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    leaves(child, prefix ? `${prefix}.${key}` : key),
  );
}

function lookup(key: string): string {
  const value = key
    .split(".")
    .reduce<unknown>(
      (node, part) =>
        typeof node === "object" && node !== null
          ? (node as Record<string, unknown>)[part]
          : undefined,
      en,
    );
  expect(value, `${key} is missing from en.json`).toBeTypeOf("string");
  return value as string;
}

describe("glossary compliance", () => {
  const glossary = readFileSync(GLOSSARY, "utf8");

  it.each(DISCLOSURES)("%s matches the glossary exactly", (key, expected) => {
    expect(lookup(key)).toBe(expected);
  });

  it.each(DISCLOSURES)("%s is the text the glossary actually records", (_key, expected) => {
    // Guards the other direction: editing the glossary without editing the UI
    // must fail too, or the two drift apart and the test still passes.
    expect(glossary, `"${expected}" is not in docs/GLOSSARY.md`).toContain(expected);
  });

  it("uses no banned vocabulary", () => {
    const offenders: string[] = [];

    for (const [key, text] of leaves(en)) {
      if (key.startsWith("_")) continue;
      for (const word of BANNED) {
        if (NEGATED[key]?.includes(word)) continue;
        if (new RegExp(`\\b${word}\\b`, "i").test(text)) {
          offenders.push(`${key}: "${word}" in "${text}"`);
        }
      }
    }

    expect(
      offenders,
      `Banned vocabulary (docs/GLOSSARY.md §1):\n  ${offenders.join("\n  ")}`,
    ).toEqual([]);
  });

  it("names the three outcomes the way the glossary does", () => {
    expect(lookup("outcome.clear")).toBe("Clear");
    expect(lookup("outcome.clearWithConditions")).toBe("Clear, with one condition");
    expect(lookup("outcome.humanReviewRequired")).toBe("Needs a person to look at this");
  });

  it("never calls human review an error", () => {
    // "Never render the third as an error. Not in colour, not in wording, not in
    // layout." The wording half is checkable here.
    const review = [lookup("outcome.humanReviewRequired"), lookup("review.heading"), lookup("review.body")];
    for (const text of review) {
      expect(text).not.toMatch(/\b(error|failed|failure|unavailable|sorry|unable)\b/i);
    }
  });

  it("writes currency the way the glossary requires", () => {
    // "written AED 80,000 ... Never '80K', never 'Dhs'."
    for (const [key, text] of leaves(en)) {
      expect(text, `${key} uses a banned currency form`).not.toMatch(/\bDhs\b|\b\d+K\b/);
    }
    expect(lookup("checker.currency")).toBe("AED");
  });
});
