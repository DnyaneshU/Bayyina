import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type EvaluationRecord } from "../api/client";

/**
 * The rent-increase checker.
 *
 * Three amounts in, one result out, with the clause it came from. The market
 * average is entered by hand for now — automatic comparables arrive in T2.3 —
 * and that is stated on the field rather than hidden, because an answer built on
 * a figure the reader supplied is only as good as that figure.
 *
 * The request therefore omits `contract_count`, which makes the backend return
 * CLEAR_WITH_CONDITIONS naming `market_average_not_derived`. Sending an invented
 * count to obtain a clean CLEAR would be fabricating evidence.
 */

const RENT_RULE = "rent_increase.dubai.decree_43_2013";

type FieldName = "current_annual_rent" | "market_average_rent" | "proposed_annual_rent";

const FIELDS: Array<{ name: FieldName; labelKey: string; helpKey: string }> = [
  {
    name: "current_annual_rent",
    labelKey: "field.currentRent",
    helpKey: "field.currentRentHelp",
  },
  {
    name: "proposed_annual_rent",
    labelKey: "field.proposedRent",
    helpKey: "field.proposedRentHelp",
  },
  {
    name: "market_average_rent",
    labelKey: "field.marketAverage",
    helpKey: "checker.marketAverageHelp",
  },
];

const EMPTY: Record<FieldName, string> = {
  current_annual_rent: "",
  proposed_annual_rent: "",
  market_average_rent: "",
};

/** Outcome colour. Human review is considered, never failure (docs/GLOSSARY.md). */
const OUTCOME_COLOUR: Record<EvaluationRecord["state"], string> = {
  CLEAR: "var(--color-clear)",
  CLEAR_WITH_CONDITIONS: "var(--color-conditional)",
  HUMAN_REVIEW_REQUIRED: "var(--color-review)",
};

function formatAed(value: string | number | undefined): string {
  if (value === undefined) return "";
  const amount = Number(value);
  if (Number.isNaN(amount)) return String(value);
  // Grouped, no decimals when whole: "AED 80,000" per the glossary, never "80K".
  return amount.toLocaleString("en-AE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatPercent(value: string | number | undefined): string {
  if (value === undefined) return "";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export default function Checker() {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<FieldName, string>>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [record, setRecord] = useState<EvaluationRecord | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSource, setShowSource] = useState(false);

  function validate(): boolean {
    const found: Partial<Record<FieldName, string>> = {};
    for (const { name } of FIELDS) {
      const raw = values[name].trim();
      if (!raw) found[name] = t("validation.required");
      else if (!/^\d+(\.\d{1,2})?$/.test(raw)) found[name] = t("validation.notANumber");
      else if (Number(raw) <= 0) found[name] = t("validation.mustBePositive");
    }
    setErrors(found);
    return Object.keys(found).length === 0;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFailure(null);
    if (!validate()) return;

    setBusy(true);
    try {
      const result = await api.evaluate({
        rule_id: RENT_RULE,
        // Strings, never numbers: rent is currency and the backend refuses a float.
        inputs: {
          current_annual_rent: values.current_annual_rent.trim(),
          market_average_rent: values.market_average_rent.trim(),
          proposed_annual_rent: values.proposed_annual_rent.trim(),
        },
        input_sources: {
          current_annual_rent: "caller_stated",
          market_average_rent: "user_supplied",
          proposed_annual_rent: "caller_stated",
        },
        // No contract_count: we did not derive this figure, and saying we did
        // would be inventing evidence.
        market: { snapshot_id: "user_supplied" },
      });
      setRecord(result);
    } catch (error) {
      setFailure(
        error instanceof ApiError ? error.message : t("status.serviceUnavailable"),
      );
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setValues(EMPTY);
    setErrors({});
    setRecord(null);
    setFailure(null);
    setShowSource(false);
  }

  if (record) {
    return (
      <Result
        record={record}
        showSource={showSource}
        onToggleSource={() => setShowSource((open) => !open)}
        onReset={reset}
      />
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t("checker.heading")}</h2>
        <p className="mt-1 text-sm text-[--color-ink-500]">{t("checker.intro")}</p>
      </div>

      {FIELDS.map(({ name, labelKey, helpKey }) => (
        <div key={name}>
          <label htmlFor={name} className="block font-medium">
            {t(labelKey)}
          </label>
          <p id={`${name}-help`} className="mt-1 mb-2 text-sm text-[--color-ink-500]">
            {t(helpKey)}
          </p>
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="text-sm text-[--color-ink-500]">
              {t("checker.currency")}
            </span>
            <input
              id={name}
              name={name}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={values[name]}
              aria-describedby={errors[name] ? `${name}-error` : `${name}-help`}
              aria-invalid={errors[name] ? true : undefined}
              onChange={(event) =>
                setValues((current) => ({ ...current, [name]: event.target.value }))
              }
              className="w-full rounded border border-[--color-rule] bg-[--color-paper-raised] px-3 py-2 text-lg"
            />
          </div>
          {errors[name] && (
            <p id={`${name}-error`} role="alert" className="mt-1 text-sm text-[--color-danger]">
              {errors[name]}
            </p>
          )}
        </div>
      ))}

      {failure && (
        <p role="alert" className="text-[--color-danger]">
          {failure}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded bg-[--color-ink-900] px-4 py-3 font-medium text-white disabled:opacity-60"
      >
        {busy ? t("checker.submitting") : t("checker.submit")}
      </button>
    </form>
  );
}

function Result({
  record,
  showSource,
  onToggleSource,
  onReset,
}: {
  record: EvaluationRecord;
  showSource: boolean;
  onToggleSource: () => void;
  onReset: () => void;
}) {
  const { t } = useTranslation();
  const review = record.state === "HUMAN_REVIEW_REQUIRED";

  const outcomeLabel = {
    CLEAR: t("outcome.clear"),
    CLEAR_WITH_CONDITIONS: t("outcome.clearWithConditions"),
    HUMAN_REVIEW_REQUIRED: t("outcome.humanReviewRequired"),
  }[record.state];

  return (
    <section aria-labelledby="result-heading" className="space-y-6">
      <div>
        <p
          className="text-sm font-semibold tracking-wide uppercase"
          style={{ color: OUTCOME_COLOUR[record.state] }}
        >
          {outcomeLabel}
        </p>
        <h2 id="result-heading" className="mt-1 text-2xl font-semibold">
          {review
            ? t("review.heading")
            : record.verdict === "permitted"
              ? t("result.permitted")
              : t("result.notPermitted")}
        </h2>
      </div>

      {review ? (
        <div className="rounded border border-[--color-rule] bg-[--color-paper-raised] p-4">
          <p>{t("review.body", { count: record.evidence?.contract_count ?? 0 })}</p>
          <p className="mt-2 text-sm text-[--color-ink-500]">{t("review.stillTrue")}</p>
        </div>
      ) : (
        <>
          {record.conditions.length > 0 && (
            <div
              className="rounded border-s-4 bg-[--color-paper-raised] p-4"
              style={{ borderInlineStartColor: "var(--color-conditional)" }}
            >
              <h3 className="font-medium">{t("condition.heading")}</h3>
              <ul className="mt-2 space-y-1 text-sm">
                {record.conditions.map((condition) => (
                  <li key={condition}>
                    {t(`condition.${condition}`, {
                      count: record.evidence?.contract_count ?? 0,
                    })}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <dl className="rounded border border-[--color-rule] bg-[--color-paper-raised] p-4">
            <h3 className="mb-3 text-sm font-semibold tracking-wide uppercase">
              {t("result.howWeGotThere")}
            </h3>
            <Row
              label={t("result.gapBelowMarket")}
              value={formatPercent(record.computed.gap_pct)}
            />
            <Row
              label={t("result.permittedIncrease")}
              value={formatPercent(record.computed.max_increase_pct)}
            />
            <Row
              label={t("result.proposedIncrease")}
              value={formatPercent(record.computed.proposed_increase_pct)}
            />
            <Row
              label={t("result.maxLawfulRent")}
              value={`${t("checker.currency")} ${formatAed(record.computed.max_lawful_rent)}`}
              emphasis
            />
          </dl>
        </>
      )}

      <div className="rounded border border-[--color-rule] bg-[--color-paper-raised] p-4">
        <h3 className="text-sm font-semibold tracking-wide uppercase">{t("result.rule")}</h3>
        <p className="mt-2 font-medium">{record.citation.title}</p>
        <p className="text-sm text-[--color-ink-500]">{record.citation.clause}</p>

        <button
          type="button"
          onClick={onToggleSource}
          aria-expanded={showSource}
          className="mt-2 text-sm underline"
        >
          {showSource ? t("result.hideSource") : t("result.showSource")}
        </button>
        {showSource && (
          <blockquote className="mt-2 border-s-2 border-[--color-rule] ps-3 text-sm whitespace-pre-line">
            {record.citation.verbatim}
          </blockquote>
        )}

        <p className="mt-3 text-xs text-[--color-ink-500]">
          {t("result.ruleVersion")} {record.rule_version} ·{" "}
          <code className="break-all">{record.rule_signature.slice(0, 23)}…</code>
        </p>
      </div>

      <p className="rounded bg-[--color-paper-raised] p-3 text-sm text-[--color-ink-700]">
        {t("disclosure.provisional")}
      </p>
      <p className="text-sm text-[--color-ink-500]">{t("disclosure.callerStated")}</p>

      <button
        type="button"
        onClick={onReset}
        className="w-full rounded border border-[--color-ink-700] px-4 py-3 font-medium"
      >
        {t("checker.startOver")}
      </button>
    </section>
  );
}

function Row({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4 border-t border-[--color-rule] py-2 first:border-t-0">
      <dt className="text-[--color-ink-500]">{label}</dt>
      <dd className={emphasis ? "font-semibold" : undefined}>{value}</dd>
    </div>
  );
}
