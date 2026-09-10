import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type HealthResponse } from "./api/client";
import Checker from "./components/Checker";
import {
  AVAILABLE_LANGUAGES,
  LANGUAGES,
  type LanguageCode,
  applyLanguage,
  storedLanguage,
} from "./i18n";

/**
 * The shell: language switch, the checker, and the standing disclosures.
 *
 * Backend state is shown only when the service is unreachable or the corpus is
 * unsigned. A green panel on every load is noise; the absence of one is the
 * signal, and a corpus that is not signed is something a reader deserves to see.
 *
 * The switcher offers only the languages the interface can actually render, and
 * disappears entirely while there is just one. Arabic and Malayalam are still
 * the product — see docs/GLOSSARY.md §6 — but a control that changes nothing is
 * a broken control, however carefully it is captioned (D-065).
 */
export default function App() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState<LanguageCode>(
    () => storedLanguage() ?? "en",
  );
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    applyLanguage(language);
  }, [language]);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError
            ? err.message
            : t("status.serviceUnavailable"),
        );
      });
  }, [t]);

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <header className="mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-3xl font-semibold text-ink-900">
            {t("product.name")}
          </h1>
          {AVAILABLE_LANGUAGES.length > 1 && (
            <nav aria-label={t("language.switcher")} className="flex gap-1">
              {AVAILABLE_LANGUAGES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => setLanguage(code)}
                  aria-pressed={language === code}
                  className={`rounded border px-3 py-2 text-sm ${
                    language === code
                      ? "border-ink-700 bg-ink-700 text-white"
                      : "border-edge bg-paper-raised text-ink-700"
                  }`}
                >
                  {LANGUAGES[code].label}
                </button>
              ))}
            </nav>
          )}
        </div>
        <p className="mt-1 text-ink-500">{t("product.tagline")}</p>
      </header>

      {error && (
        <p
          role="alert"
          className="mb-6 rounded bg-paper-raised p-3 text-danger"
        >
          {error}
        </p>
      )}
      {health && !health.corpus_signed && (
        <p
          role="alert"
          className="mb-6 rounded bg-paper-raised p-3 text-danger"
        >
          {t("status.serviceUnavailable")}
        </p>
      )}

      <Checker />

      <footer className="mt-10 space-y-1 border-t border-rule pt-4 text-xs text-ink-500">
        <p>{t("disclosure.notAdvice")}</p>
        <p>{t("disclosure.notOfficial")}</p>
      </footer>
    </main>
  );
}
