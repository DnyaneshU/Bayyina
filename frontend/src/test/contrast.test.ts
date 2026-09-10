import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The palette, measured rather than believed.
 *
 * T2.0 asks for "colour with **WCAG AA contrast verified**". A comment saying a
 * palette passes is not verification — it is a claim that was true when someone
 * typed it. Two tokens were failing when this file was written:
 *
 *   * `ink-300` at **2.46:1**, well under AA, defined and used by nothing
 *   * `rule` at **1.26:1**, on the border of the rent input — the one field a
 *     person has to find and type into
 *
 * The audience is stated in the plan: a competent adult reader in their second
 * or third language, on a small phone, often in bright sunlight. Contrast is
 * not a compliance checkbox for them.
 */

const CSS = readFileSync(join(__dirname, "..", "index.css"), "utf8");

/** Every `--color-*` token declared in `@theme`. */
const TOKENS: Record<string, string> = Object.fromEntries(
  [...CSS.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map(
    ([, name, value]) => [name, value],
  ),
);

const GROUNDS = ["paper", "paper-raised"] as const;

/** Tokens that carry text. Everything else is a boundary or a ground. */
const INK = ["ink-900", "ink-700", "ink-500"] as const;

/** Outcome colours. Used as text on a ground, and as a ground under white. */
const OUTCOMES = ["clear", "conditional", "review", "danger"] as const;

function relativeLuminance(hex: string): number {
  const channel = (offset: number) => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [high, low] = [relativeLuminance(a), relativeLuminance(b)].sort(
    (x, y) => y - x,
  );
  return (high + 0.05) / (low + 0.05);
}

function token(name: string): string {
  const value = TOKENS[name];
  expect(value, `--color-${name} is not declared in index.css`).toBeDefined();
  return value;
}

describe("the palette meets WCAG AA", () => {
  it("declares every token the interface names", () => {
    for (const name of [...INK, ...OUTCOMES, ...GROUNDS, "rule", "edge"]) {
      expect(TOKENS, `--color-${name} is missing`).toHaveProperty(name);
    }
  });

  describe.each(GROUNDS)("on --color-%s", (ground) => {
    it.each(INK)("%s reaches 4.5:1 for body text", (ink) => {
      const ratio = contrast(token(ink), token(ground));
      expect(
        ratio,
        `${ink} on ${ground} is ${ratio.toFixed(2)}:1, AA needs 4.5`,
      ).toBeGreaterThanOrEqual(4.5);
    });

    it.each(OUTCOMES)(
      "%s reaches 4.5:1, because an outcome is read as text",
      (outcome) => {
        const ratio = contrast(token(outcome), token(ground));
        expect(
          ratio,
          `${outcome} on ${ground} is ${ratio.toFixed(2)}:1, AA needs 4.5`,
        ).toBeGreaterThanOrEqual(4.5);
      },
    );
  });

  it.each(OUTCOMES)(
    "white on %s reaches 4.5:1, for a filled chip",
    (outcome) => {
      const ratio = contrast("#ffffff", token(outcome));
      expect(
        ratio,
        `white on ${outcome} is ${ratio.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(4.5);
    },
  );
});

describe("boundaries a person has to find", () => {
  it.each(GROUNDS)("--color-edge reaches 3:1 on %s", (ground) => {
    // WCAG 1.4.11. The outline of a field someone must type into is not
    // decoration — if they cannot see where it is, they cannot use the form.
    const ratio = contrast(token("edge"), token(ground));
    expect(
      ratio,
      `edge on ${ground} is ${ratio.toFixed(2)}:1, non-text UI needs 3:1`,
    ).toBeGreaterThanOrEqual(3);
  });

  it("keeps `rule` weaker than `edge`, or the distinction has collapsed", () => {
    // Two weights on purpose. If they converge, either every hairline has become
    // shouty or every field boundary has become invisible again.
    expect(contrast(token("edge"), token("paper"))).toBeGreaterThan(
      contrast(token("rule"), token("paper")),
    );
  });

  it("keeps the focus ring findable", () => {
    // Removing an outline is the single most common accessibility regression,
    // and the ring colour has to work on both grounds.
    //
    // The first version of this asserted only that `outline:` appeared, which
    // `outline: none` satisfies — deleting the ring left it green. It has to
    // assert a *visible* outline.
    const block = /:focus-visible\s*\{([^}]*)\}/.exec(CSS);
    expect(block, ":focus-visible has no rule at all").not.toBeNull();
    const outline = /outline:\s*([^;]+);/.exec(block![1]);
    expect(outline, ":focus-visible declares no outline").not.toBeNull();
    expect(outline![1].trim(), "the focus ring was switched off").not.toMatch(
      /^(none|0|hidden)$/,
    );
    for (const ground of GROUNDS) {
      expect(contrast(token("review"), token(ground))).toBeGreaterThanOrEqual(
        3,
      );
    }
  });
});

/**
 * The opening tag of a JSX element, from `<name` to its closing `>`.
 *
 * A regex cannot do this, and two earlier versions of the test below proved it
 * by staying green while the exact defect they were written for was put back:
 *
 *   * scanning line by line missed a `className` five lines under its `<input`
 *   * `[^>]*` stopped at the first `>`, and `onChange={(e) => ...}` has one
 *
 * So brace depth is tracked, and comments inside the tag are stripped — a
 * comment explaining why a token was replaced names the token it replaced, and
 * the version after those two flagged its own explanation as the defect.
 */
function openingTags(
  source: string,
  names: readonly string[],
): { name: string; text: string }[] {
  const found: { name: string; text: string }[] = [];

  for (const name of names) {
    for (const start of source.matchAll(new RegExp(`<${name}\\b`, "g"))) {
      let depth = 0;
      let index = start.index! + name.length + 1;
      while (index < source.length) {
        const character = source[index];
        if (character === "{") depth += 1;
        else if (character === "}") depth -= 1;
        else if (character === ">" && depth === 0) break;
        index += 1;
      }
      const text = source
        .slice(start.index!, index + 1)
        .replace(/\/\/[^\n]*/g, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      found.push({ name, text });
    }
  }
  return found;
}

describe("the tokens that were removed", () => {
  it("does not bring back ink-300", () => {
    // 2.46:1. It failed AA and nothing used it. A token that exists will
    // eventually be reached for.
    expect(TOKENS).not.toHaveProperty("ink-300");
  });

  it("finds the elements it is meant to be checking", () => {
    // The guard on the guard. Both earlier versions of the test below passed
    // because they matched *nothing* — a scan that finds no elements cannot
    // find a defect in one, and reports success either way.
    const source = readFileSync(
      join(__dirname, "../components/Checker.tsx"),
      "utf8",
    );
    const tags = openingTags(source, ["input", "button"]);

    expect(
      tags.length,
      "no input or button elements were found at all",
    ).toBeGreaterThan(2);
    expect(
      tags.some((tag) => tag.name === "input" && /className=/.test(tag.text)),
      "an <input> was found but its className was not — the scan stops short",
    ).toBe(true);
  });

  it("keeps `rule` off anything a person has to find", () => {
    // The defect this file was written for: the rent input's border was
    // `border-rule` at 1.26:1, which is not a visible boundary.
    const offenders: string[] = [];

    for (const file of ["../App.tsx", "../components/Checker.tsx"]) {
      const source = readFileSync(join(__dirname, file), "utf8");
      for (const tag of openingTags(source, [
        "input",
        "button",
        "select",
        "textarea",
      ])) {
        if (/\bborder-rule\b/.test(tag.text)) {
          offenders.push(`${file}: <${tag.name}> carries border-rule`);
        }
      }
    }

    expect(
      offenders,
      `a 1.26:1 hairline on something interactive: ${offenders.join("; ")}`,
    ).toEqual([]);
  });
});
