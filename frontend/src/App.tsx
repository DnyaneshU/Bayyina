import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type HealthResponse } from "./api/client";
import Checker from "./components/Checker";
import { LANGUAGES, type LanguageCode, applyLanguage } from "./i18n";

/**
 * The shell: language switch, the checker, and the standing disclosures.
 *
 * Backend state is shown only when the service is unreachable or the corpus is
 * unsigned. A green panel on every load is noise; the absence of one is the
 * signal, and a corpus that is not signed is something a reader deserves to see.
 */
export default function App() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState<LanguageCode>("en");
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
        setError(err instanceof ApiError ? err.message : t("status.serviceUnavailable"));
      });
  }, [t]);

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <header className="mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-3xl font-semibold text-[--color-ink-900]">{t("product.name")}</h1>
          <nav aria-label="Language" className="flex gap-1">
            {(Object.keys(LANGUAGES) as LanguageCode[]).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setLanguage(code)}
                aria-pressed={language === code}
                className={`rounded border px-3 py-2 text-sm ${
                  language === code
                    ? "border-[--color-ink-700] bg-[--color-ink-700] text-white"
                    : "border-[--color-rule] bg-white text-[--color-ink-700]"
                }`}
              >
                {LANGUAGES[code].label}
              </button>
            ))}
          </nav>
        </div>
        <p className="mt-1 text-[--color-ink-500]">{t("product.tagline")}</p>
      </header>

      {error && (
        <p role="alert" className="mb-6 rounded bg-[--color-paper-raised] p-3 text-[--color-danger]">
          {error}
        </p>
      )}
      {health && !health.corpus_signed && (
        <p role="alert" className="mb-6 rounded bg-[--color-paper-raised] p-3 text-[--color-danger]">
          {t("status.serviceUnavailable")}
        </p>
      )}

      <Checker />

      <footer className="mt-10 space-y-1 border-t border-[--color-rule] pt-4 text-xs text-[--color-ink-500]">
        <p>{t("disclosure.notAdvice")}</p>
        <p>{t("disclosure.notOfficial")}</p>
      </footer>
    </main>
  );
}
