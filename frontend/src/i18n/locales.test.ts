import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  LANGUAGES,
  type LanguageCode,
  isTranslated,
  translationStatus,
} from ".";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import ml from "./locales/ml.json";

/**
 * Translation is either declared absent, or complete. Never a silent half-state.
 *
 * English is authoritative (docs/GLOSSARY.md). A locale may say "not translated"
 * by carrying `_TRANSLATION_STATUS`, in which case i18next falls back to English
 * and the gap is obvious. Once that marker is removed the locale is claiming to
 * be translated, and it must actually cover every key.
 *
 * Without this, someone translates 40% of a file, removes the marker, and the
 * remaining 60% silently renders in English inside an otherwise Arabic
 * interface — which for a legal disclosure is worse than showing nothing.
 */

const MARKER = "_TRANSLATION_STATUS";
const LOCALES: Record<string, Record<string, unknown>> = { ar, ml };

function leafKeys(obj: unknown, prefix = ""): string[] {
  if (typeof obj !== "object" || obj === null) return [prefix];
  return Object.entries(obj as Record<string, unknown>).flatMap(
    ([key, value]) =>
      key === MARKER ? [] : leafKeys(value, prefix ? `${prefix}.${key}` : key),
  );
}

describe("locale files", () => {
  const englishKeys = leafKeys(en);

  it("English defines every key the interface uses", () => {
    expect(englishKeys.length).toBeGreaterThan(20);
    expect(englishKeys).toContain("disclosure.notAdvice");
    expect(englishKeys).toContain("disclosure.provisional");
    expect(englishKeys).toContain("outcome.humanReviewRequired");
  });

  it.each(Object.entries(LOCALES))(
    "%s is either declared untranslated, or complete",
    (code, locale) => {
      const declaredUntranslated = MARKER in locale;

      if (declaredUntranslated) {
        const status = String(locale[MARKER]);
        // The marker is a working instruction to a translator, not a TODO.
        expect(status, `${code}: marker must name the source of truth`).toMatch(
          /GLOSSARY/,
        );
        expect(
          status,
          `${code}: marker must forbid machine translation`,
        ).toMatch(/[Mm]achine translation is not acceptable/);
        return;
      }

      const missing = englishKeys.filter((key) =>
        key
          .split(".")
          .reduce<unknown>(
            (node, part) =>
              typeof node === "object" && node !== null
                ? (node as Record<string, unknown>)[part]
                : undefined,
            locale,
          ) === undefined
          ? true
          : false,
      );

      expect(
        missing,
        `${code} removed the untranslated marker but is missing ${missing.length} key(s). ` +
          `Either finish the translation or restore the marker.`,
      ).toEqual([]);
    },
  );

  it("no interface code references an underscore-prefixed key", () => {
    // Marker keys are metadata for translators. If one were ever rendered, an
    // instruction to a translator would appear in the product.
    const src = join(__dirname, "..");
    const files = readdirSync(src, {
      recursive: true,
      encoding: "utf8",
    }).filter(
      (f) =>
        (f.endsWith(".tsx") || f.endsWith(".ts")) &&
        !f.includes("locales.test"),
    );
    const offenders = files.filter((f) => {
      try {
        return /t\(\s*["'`]_/.test(readFileSync(join(src, f), "utf8"));
      } catch {
        return false;
      }
    });
    expect(offenders).toEqual([]);
  });

  it("reports a locale as translated exactly when it carries no marker", () => {
    // The marker is the single source of truth. The switcher's dot and the
    // interface's disclosure both derive from `isTranslated`, so finishing a
    // translation removes the marker and the disclosure disappears with it —
    // there is no second place to remember to update.
    for (const code of Object.keys(LANGUAGES) as LanguageCode[]) {
      const locale = code === "en" ? en : LOCALES[code];
      expect(isTranslated(code), `${code} disagrees with its own marker`).toBe(
        !(MARKER in locale),
      );
    }
  });

  it("keeps English translated, since it is the source", () => {
    expect(isTranslated("en")).toBe(true);
    expect(translationStatus("en")).toBeNull();
  });

  it("hands a translator the instruction, not a TODO", () => {
    // Whoever picks this up should learn what to do from the file itself.
    for (const code of ["ar", "ml"] as LanguageCode[]) {
      const status = translationStatus(code);
      expect(
        status,
        `${code} has no status to give a translator`,
      ).not.toBeNull();
      expect(status).toMatch(/GLOSSARY/);
    }
  });
});
