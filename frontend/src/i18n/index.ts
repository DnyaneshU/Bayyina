import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ar from "./locales/ar.json";
import en from "./locales/en.json";
import ml from "./locales/ml.json";

/**
 * Every language Bayyina is being built for.
 *
 * All three are the product, not a nice-to-have: **no phone channel in Dubai
 * answers a tenancy question in Malayalam**, which is a headline claim on the
 * canvas and a large part of why this exists. They are listed here in full even
 * while only some are translated, because this is the roadmap and the PDF
 * templates and voice scripts read from the same set.
 */
export const LANGUAGES = {
  en: { label: "English", dir: "ltr" },
  ar: { label: "العربية", dir: "rtl" },
  ml: { label: "മലയാളം", dir: "ltr" },
} as const;

export type LanguageCode = keyof typeof LANGUAGES;

const RESOURCES: Record<LanguageCode, Record<string, unknown>> = { en, ar, ml };

/**
 * A locale declares itself untranslated by carrying `_TRANSLATION_STATUS`
 * (D-022). That marker is the single source of truth for everything downstream.
 */
const TRANSLATION_MARKER = "_TRANSLATION_STATUS";

export function isTranslated(code: LanguageCode): boolean {
  return !(TRANSLATION_MARKER in RESOURCES[code]);
}

/** Why a locale is untranslated — the instruction left for the translator. */
export function translationStatus(code: LanguageCode): string | null {
  const value = RESOURCES[code][TRANSLATION_MARKER];
  return typeof value === "string" ? value : null;
}

/**
 * The languages the interface can actually render, derived rather than listed.
 *
 * The switcher offers exactly these. It once offered all three, and Arabic
 * differed from English in 1 of 57 strings while Malayalam differed in **zero** —
 * so two of the buttons changed nothing on screen, which is a broken control
 * however carefully it is explained.
 *
 * Because this is computed from the marker, filling in `ar.json` and removing
 * its marker makes the Arabic button appear on its own. There is no second place
 * to remember, and no chance of shipping a language the interface cannot speak.
 */
export const AVAILABLE_LANGUAGES: LanguageCode[] = (
  Object.keys(LANGUAGES) as LanguageCode[]
).filter(isTranslated);

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
    ml: { translation: ml },
  },
  lng: "en",
  // English is authoritative (see docs/GLOSSARY.md). Untranslated keys fall
  // back to English rather than rendering a raw key, so a partly finished
  // translation degrades to something readable instead of something broken.
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

const STORAGE_KEY = "bayyina.language";

/**
 * The language chosen on a previous visit, if we can still render it.
 *
 * Someone who has to re-pick their language on every visit stops picking it.
 * The availability check matters in one direction: if a translation is ever
 * withdrawn — a marker restored because a reviewer found a problem — a returning
 * reader must not be pinned to a locale we have just stopped standing behind.
 *
 * Storage can throw outright in a private window or with site data blocked, so
 * every access is guarded and an unreadable store simply means "no preference".
 *
 * Deliberately not `navigator.language`: auto-selecting a locale we have not
 * translated would greet an Arabic browser with a mirrored English page it did
 * not ask for. Detection belongs with the translations, not before them.
 */
export function storedLanguage(): LanguageCode | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === null || !(value in LANGUAGES)) return null;
    const code = value as LanguageCode;
    return isTranslated(code) ? code : null;
  } catch {
    return null;
  }
}

/**
 * Apply a language to the document.
 *
 * Sets both `lang` and `dir` on <html>. RTL is a layout concern, not a font
 * swap: setting dir mirrors the whole page because components use logical
 * properties. `lang` also drives the per-script font stack in index.css.
 *
 * Accepts any language in `LANGUAGES`, not only the available ones. The gate
 * belongs on the switcher; this function is also how the RTL foundation stays
 * exercised while Arabic is still being translated.
 */
export function applyLanguage(code: LanguageCode): void {
  void i18n.changeLanguage(code);
  document.documentElement.lang = code;
  document.documentElement.dir = LANGUAGES[code].dir;
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // A preference we cannot persist is not worth failing a render over.
  }
}

export default i18n;
