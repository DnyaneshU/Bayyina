import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type Dwelling, type EvaluationRecord } from "../api/client";

/**
 * The rent-increase checker.
 *
 * The market average can come from one of two places, and which one it was is
 * never left implicit. Give us the area, property type and bedrooms and we
 * derive the figure from registered tenancy contracts, recording it as ours.
 * Supply the figure yourself and we apply the rule to exactly that number,
 * recording it as yours — and omitting `contract_count`, so the backend returns
 * CLEAR_WITH_CONDITIONS naming `market_average_not_derived`. Sending an invented
 * count to obtain a clean CLEAR would be fabricating evidence.
 *
 * Deriving is offered only when the service can actually do it. The comparables
 * database is optional at boot (D-074) and absent from the published image, so
 * `/areas` answering 503 is a supported state: the choice disappears, the manual
 * path stays, and the page says why rather than presenting a control that
 * cannot work.
 */

const RENT_RULE = "rent_increase.dubai.decree_43_2013";

type FieldName =
  "current_annual_rent" | "market_average_rent" | "proposed_annual_rent";

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

/**
 * Hand the reader a file.
 *
 * A blob and an anchor rather than navigating to the endpoint: the pack is a
 * POST, and it must not be reachable by URL. A link someone could paste into a
 * chat would be a link to a document about their tenancy.
 */
function saveTextFile(text: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

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
  const { t, i18n } = useTranslation();
  const [values, setValues] = useState<Record<FieldName, string>>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [record, setRecord] = useState<EvaluationRecord | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSource, setShowSource] = useState(false);

  // Where the market average comes from. `null` while we are still finding out
  // whether we can derive one at all.
  const [areas, setAreas] = useState<string[] | null>(null);
  const [marketUsable, setMarketUsable] = useState<boolean | null>(null);
  const [mode, setMode] = useState<"derive" | "manual">("manual");
  const [dwelling, setDwelling] = useState<{
    area: string;
    kind: Dwelling["kind"];
    bedrooms: string;
  }>({ area: "", kind: "flat", bedrooms: "" });
  const [dwellingErrors, setDwellingErrors] = useState<Record<string, string>>({});
  const [packBusy, setPackBusy] = useState(false);
  const [packError, setPackError] = useState<string | null>(null);

  useEffect(() => {
    // The comparables database is optional at boot (D-074) and absent from the
    // published image, so `/areas` answering 503 is a supported state rather
    // than a fault. When it does, we say plainly that we cannot work out an
    // average and leave the manual path working — which is the whole product
    // minus one convenience, not a broken page.
    api
      .areas()
      .then((response) => {
        setAreas(response.areas);
        setMarketUsable(true);
        setMode("derive");
      })
      .catch(() => {
        setAreas([]);
        setMarketUsable(false);
        setMode("manual");
      });
  }, []);

  /** The money fields this mode actually asks for. */
  function activeFields() {
    return mode === "derive"
      ? FIELDS.filter((field) => field.name !== "market_average_rent")
      : FIELDS;
  }

  function validate(): boolean {
    const found: Partial<Record<FieldName, string>> = {};
    for (const { name } of activeFields()) {
      const raw = values[name].trim();
      if (!raw) found[name] = t("validation.required");
      else if (!/^\d+(\.\d{1,2})?$/.test(raw))
        found[name] = t("validation.notANumber");
      else if (Number(raw) <= 0) found[name] = t("validation.mustBePositive");
    }
    setErrors(found);

    const dwellingFound: Record<string, string> = {};
    if (mode === "derive") {
      if (!dwelling.area.trim()) dwellingFound.area = t("validation.pickArea");
      const bedrooms = dwelling.bedrooms.trim();
      if (!/^\d{1,2}$/.test(bedrooms))
        dwellingFound.bedrooms = t("validation.bedrooms");
    }
    setDwellingErrors(dwellingFound);

    return (
      Object.keys(found).length === 0 && Object.keys(dwellingFound).length === 0
    );
  }

  /** The evaluation, built once so the checker and the pack cannot disagree. */
  function buildRequest() {
    const common = {
      rule_id: RENT_RULE,
      // Strings, never numbers: rent is currency and the backend refuses a float.
      inputs: {
        current_annual_rent: values.current_annual_rent.trim(),
        proposed_annual_rent: values.proposed_annual_rent.trim(),
      } as Record<string, string>,
      input_sources: {
        current_annual_rent: "caller_stated",
        proposed_annual_rent: "caller_stated",
      } as Record<string, string>,
    };

    if (mode === "derive") {
      // The dwelling instead of a figure. The backend looks up the comparable
      // and records the source as ours, so we never label a derived number as
      // caller-supplied or the reverse.
      return {
        ...common,
        dwelling: {
          area: dwelling.area.trim(),
          kind: dwelling.kind,
          bedrooms: Number(dwelling.bedrooms.trim()),
        },
      };
    }

    return {
      ...common,
      inputs: {
        ...common.inputs,
        market_average_rent: values.market_average_rent.trim(),
      },
      input_sources: {
        ...common.input_sources,
        market_average_rent: "user_supplied",
      },
      // No contract_count: we did not derive this figure, and saying we did
      // would be inventing evidence.
      market: { snapshot_id: "user_supplied" },
    };
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFailure(null);
    if (!validate()) return;

    setBusy(true);
    try {
      setRecord(await api.evaluate(buildRequest()));
    } catch (error) {
      setFailure(
        error instanceof ApiError
          ? error.message
          : t("status.serviceUnavailable"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function downloadPack(reference: string) {
    setPackError(null);
    setPackBusy(true);
    try {
      // The evaluation is posted again, not the record. The backend recomputes
      // the verdict rather than trusting anything this browser assembled, which
      // is what makes the document worth carrying into a hearing (G10).
      const text = await api.evidencePack({
        ...buildRequest(),
        caller_ref: reference,
        language: i18n.language,
      });
      saveTextFile(text, `bayyina-${reference}.txt`);
    } catch {
      // The result on screen is untouched. Losing the download must not look
      // like losing the answer.
      setPackError(t("pack.failed"));
    } finally {
      setPackBusy(false);
    }
  }

  function reset() {
    setValues(EMPTY);
    setErrors({});
    setRecord(null);
    setFailure(null);
    setShowSource(false);
    setPackError(null);
  }

  if (record) {
    return (
      <Result
        record={record}
        showSource={showSource}
        onToggleSource={() => setShowSource((open) => !open)}
        onReset={reset}
        onDownload={() => downloadPack(record.eval_id)}
        packBusy={packBusy}
        packError={packError}
      />
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t("checker.heading")}</h2>
        <p className="mt-1 text-sm text-ink-500">{t("checker.intro")}</p>
      </div>

      {marketUsable === false && (
        <p className="rounded bg-paper-raised p-3 text-sm text-ink-700">
          {t("source.unavailable")}
        </p>
      )}

      {marketUsable === true && (
        <fieldset>
          <legend className="font-medium">{t("source.heading")}</legend>
          <div className="mt-2 space-y-2">
            {(["derive", "manual"] as const).map((option) => (
              <label
                key={option}
                htmlFor={`source-${option}`}
                className="flex items-start gap-2"
              >
                <input
                  id={`source-${option}`}
                  type="radio"
                  name="source"
                  value={option}
                  checked={mode === option}
                  onChange={() => setMode(option)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium">{t(`source.${option}`)}</span>
                  <span className="block text-sm text-ink-500">
                    {t(`source.${option}Help`)}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {mode === "derive" && (
        <>
          <div>
            <label htmlFor="area" className="block font-medium">
              {t("field.area")}
            </label>
            <p id="area-help" className="mt-1 mb-2 text-sm text-ink-500">
              {t("field.areaHelp")}
            </p>
            <input
              id="area"
              name="area"
              type="text"
              list="area-options"
              autoComplete="off"
              value={dwelling.area}
              aria-describedby={dwellingErrors.area ? "area-error" : "area-help"}
              aria-invalid={dwellingErrors.area ? true : undefined}
              onChange={(event) =>
                setDwelling((current) => ({ ...current, area: event.target.value }))
              }
              className="w-full rounded border border-edge bg-paper-raised px-3 py-2 text-lg"
            />
            {/*
              A datalist rather than a select: 184 areas in a dropdown is a
              scroll, and a person who knows their area wants to type it.
            */}
            <datalist id="area-options">
              {(areas ?? []).map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {dwellingErrors.area && (
              <p id="area-error" role="alert" className="mt-1 text-sm text-danger">
                {dwellingErrors.area}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="kind" className="block font-medium">
              {t("field.propertyType")}
            </label>
            <select
              id="kind"
              name="kind"
              value={dwelling.kind}
              onChange={(event) =>
                setDwelling((current) => ({
                  ...current,
                  kind: event.target.value as Dwelling["kind"],
                }))
              }
              className="mt-2 w-full rounded border border-edge bg-paper-raised px-3 py-2 text-lg"
            >
              <option value="flat">{t("field.flat")}</option>
              <option value="villa">{t("field.villa")}</option>
            </select>
          </div>

          <div>
            <label htmlFor="bedrooms" className="block font-medium">
              {t("field.bedrooms")}
            </label>
            <p id="bedrooms-help" className="mt-1 mb-2 text-sm text-ink-500">
              {t("field.bedroomsHelp")}
            </p>
            <input
              id="bedrooms"
              name="bedrooms"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={dwelling.bedrooms}
              aria-describedby={
                dwellingErrors.bedrooms ? "bedrooms-error" : "bedrooms-help"
              }
              aria-invalid={dwellingErrors.bedrooms ? true : undefined}
              onChange={(event) =>
                setDwelling((current) => ({
                  ...current,
                  bedrooms: event.target.value,
                }))
              }
              className="tabular w-full rounded border border-edge bg-paper-raised px-3 py-2 text-lg"
            />
            {dwellingErrors.bedrooms && (
              <p id="bedrooms-error" role="alert" className="mt-1 text-sm text-danger">
                {dwellingErrors.bedrooms}
              </p>
            )}
          </div>
        </>
      )}

      {activeFields().map(({ name, labelKey, helpKey }) => (
        <div key={name}>
          <label htmlFor={name} className="block font-medium">
            {t(labelKey)}
          </label>
          <p id={`${name}-help`} className="mt-1 mb-2 text-sm text-ink-500">
            {t(helpKey)}
          </p>
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="text-sm text-ink-500">
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
                setValues((current) => ({
                  ...current,
                  [name]: event.target.value,
                }))
              }
              // `border-edge`, not `border-rule`. A field a person has to type
              // into is a boundary they must be able to find: WCAG 1.4.11 asks
              // for 3:1 and `rule` manages 1.26:1. This is the rent input.
              className="tabular w-full rounded border border-edge bg-paper-raised px-3 py-2 text-lg"
            />
          </div>
          {errors[name] && (
            <p
              id={`${name}-error`}
              role="alert"
              className="mt-1 text-sm text-danger"
            >
              {errors[name]}
            </p>
          )}
        </div>
      ))}

      {failure && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded bg-ink-900 px-4 py-3 font-medium text-white disabled:opacity-60"
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
  onDownload,
  packBusy,
  packError,
}: {
  record: EvaluationRecord;
  showSource: boolean;
  onToggleSource: () => void;
  onReset: () => void;
  onDownload: () => void;
  packBusy: boolean;
  packError: string | null;
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
        <div className="rounded border border-rule bg-paper-raised p-4">
          <p>
            {t("review.body", { count: record.evidence?.contract_count ?? 0 })}
          </p>
          <p className="mt-2 text-sm text-ink-500">{t("review.stillTrue")}</p>
        </div>
      ) : (
        <>
          {record.conditions.length > 0 && (
            <div
              className="rounded border-s-4 bg-paper-raised p-4"
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

          <dl className="rounded border border-rule bg-paper-raised p-4">
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

      <div className="rounded border border-rule bg-paper-raised p-4">
        <h3 className="text-sm font-semibold tracking-wide uppercase">
          {t("result.rule")}
        </h3>
        <p className="mt-2 font-medium">{record.citation.title}</p>
        <p className="text-sm text-ink-500">{record.citation.clause}</p>

        <button
          type="button"
          onClick={onToggleSource}
          aria-expanded={showSource}
          className="mt-2 text-sm underline"
        >
          {showSource ? t("result.hideSource") : t("result.showSource")}
        </button>
        {showSource && (
          <blockquote className="mt-2 border-s-2 border-rule ps-3 text-sm whitespace-pre-line">
            {record.citation.verbatim}
          </blockquote>
        )}

        <p className="mt-3 text-xs text-ink-500">
          {t("result.ruleVersion")} {record.rule_version} ·{" "}
          <code className="break-all">
            {record.rule_signature.slice(0, 23)}…
          </code>
        </p>
      </div>

      <p className="rounded bg-paper-raised p-3 text-sm text-ink-700">
        {t("disclosure.provisional")}
      </p>
      <p className="text-sm text-ink-500">{t("disclosure.callerStated")}</p>

      {/*
        Offered for every outcome, including HUMAN_REVIEW_REQUIRED. That pack is
        the document naming which facts were missing and which rule would have
        applied — the one a person takes to the Rental Dispute Centre when we
        could not answer. Withholding it there would leave them with nothing at
        exactly the moment they need something.
      */}
      <div className="rounded border border-rule bg-paper-raised p-4">
        <h3 className="font-medium text-ink-900">{t("pack.heading")}</h3>
        <p className="mt-1 text-sm text-ink-500">{t("pack.intro")}</p>
        <button
          type="button"
          onClick={onDownload}
          disabled={packBusy}
          className="mt-3 w-full rounded border border-ink-700 px-4 py-3 font-medium disabled:opacity-60"
        >
          {packBusy ? t("pack.preparing") : t("pack.download")}
        </button>
        {packError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {packError}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="w-full rounded border border-ink-700 px-4 py-3 font-medium"
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
    <div className="flex justify-between gap-4 border-t border-rule py-2 first:border-t-0">
      <dt className="text-ink-500">{label}</dt>
      <dd className={emphasis ? "font-semibold" : undefined}>{value}</dd>
    </div>
  );
}
