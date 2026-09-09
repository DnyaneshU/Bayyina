import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ar from "./locales/ar.json";
import en from "./locales/en.json";
import ml from "./locales/ml.json";

export const LANGUAGES = {
  en: { label: "English", dir: "ltr" },
  ar: { label: "العربية", dir: "rtl" },
  ml: { label: "മലയാളം", dir: "ltr" },
} as const;

export type LanguageCode = keyof typeof LANGUAGES;

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ar: { translation: ar }, ml: { translation: ml } },
  lng: "en",
  // English is authoritative (see docs/GLOSSARY.md). Untranslated keys fall
  // back to English rather than rendering a raw key, so a missing translation
  // degrades to something readable instead of something broken.
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

/**
 * Apply a language to the document.
 *
 * Sets both `lang` and `dir` on <html>. RTL is a layout concern, not a font
 * swap: setting dir mirrors the whole page because components use logical
 * properties. `lang` also drives the per-script font stack in index.css.
 */
export function applyLanguage(code: LanguageCode): void {
  void i18n.changeLanguage(code);
  document.documentElement.lang = code;
  document.documentElement.dir = LANGUAGES[code].dir;
}

export default i18n;
