/**
 * Typed client for the Bayyina backend.
 *
 * Every response the backend sends carries `x-response-ms`. We surface it so
 * that the latency budget (<150ms p95, see README) is visible during
 * development rather than discovered at demo time.
 */

export interface RuleSummary {
  id: string;
  version: number;
  approval_status: "unsigned" | "provisional" | "certified";
  signature: string;
  clause: string;
}

export interface HealthResponse {
  status: string;
  /** Every check the service actually performed, and its result. */
  checks: Record<string, boolean>;
  /**
   * Named rather than omitted. A green health check that reports `ok` while
   * silently not looking at half the system is worse than no health check, so
   * anything unverified is listed here.
   */
  not_yet_checked: string[];
  market_data_age_days: number | null;
  corpus_signed: boolean;
  rule_count: number;
  rules: RuleSummary[];
}

/** The three outcomes, named identically in every surface (docs/GLOSSARY.md). */
export type OutcomeState = "CLEAR" | "CLEAR_WITH_CONDITIONS" | "HUMAN_REVIEW_REQUIRED";

/** Why an answer is contingent. A key, so it renders in the reader's language. */
export type Condition = "market_average_not_derived" | "thin_comparable_data";

export interface Citation {
  document_id: string;
  title: string;
  clause: string;
  url: string;
  verbatim: string;
}

export interface EvaluationRecord {
  eval_id: string;
  rule_id: string;
  rule_version: number;
  rule_signature: string;
  review_status: "unsigned" | "provisional" | "certified";
  state: OutcomeState;
  /** null whenever the outcome is HUMAN_REVIEW_REQUIRED. */
  verdict: string | null;
  inputs: Record<string, string>;
  input_sources: Record<string, string>;
  /** Empty whenever the outcome is HUMAN_REVIEW_REQUIRED. Amounts are strings. */
  computed: Record<string, string | number>;
  citation: Citation;
  evidence: { contract_count: number | null; snapshot_id: string } | null;
  conditions: Condition[];
  confidence: number | null;
  created_at: string;
}

/** Where the caller lives, so the backend can derive the market figure. */
export interface Dwelling {
  area: string;
  kind: "flat" | "villa";
  bedrooms: number;
}

export interface EvaluateRequest {
  rule_id: string;
  /**
   * Amounts as strings, never numbers. Rent is currency; a JSON float cannot
   * hold it exactly, and the backend refuses one.
   */
  inputs: Record<string, string>;
  input_sources: Record<string, string>;
  market?: { contract_count?: number | null; snapshot_id: string };
  /**
   * Send this *instead of* a market figure. Sending both is refused: the caller
   * would have no way to know which number the answer used.
   */
  dwelling?: Dwelling;
}

export interface AreasResponse {
  snapshot_id: string;
  count: number;
  areas: string[];
}

export class ApiError extends Error {
  // Declared explicitly rather than as a constructor parameter property:
  // the project sets `erasableSyntaxOnly`, which disallows syntax that cannot
  // be erased by a type-stripping transform.
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // Network failure is a first-class path, not an exception to swallow.
    throw new ApiError("The service is not reachable right now.", 0);
  }

  if (!response.ok) {
    // The backend names the offending field in `detail`. Discarding that in
    // favour of a status code would make a fixable mistake unfixable.
    const detail = await response
      .json()
      .then((body: { detail?: unknown }) =>
        typeof body.detail === "string" ? body.detail : null,
      )
      .catch(() => null);

    throw new ApiError(detail ?? `Request failed (${response.status})`, response.status);
  }

  return (await response.json()) as T;
}

/** One row of the encoded rule, generated from the table the evaluator reads. */
export interface EncodedStep {
  step: number;
  condition: string;
  outcome: string;
}

export interface ProvenanceSummary {
  rule_id: string;
  version: number;
  title: string;
  clause: string;
  approval_status: "unsigned" | "provisional" | "certified";
  signature: string | null;
  /**
   * Recomputed by the backend on every request, never echoed from the file.
   * A tampered rule carries a tampered signature block quite happily.
   */
  signature_matches: boolean;
}

export interface ProvenanceListing {
  count: number;
  rules: ProvenanceSummary[];
}

export interface RuleInputSummary {
  name: string;
  type: string;
  currency: string | null;
  required: boolean;
  /** True when we compute the value rather than being told it. Drives G5. */
  derived: boolean;
}

export interface ProvenanceDetail {
  rule_id: string;
  version: number;
  jurisdiction: string;
  effective_from: string;
  effective_to: string | null;
  citation: Omit<Citation, "verbatim">;
  /** The clause as published. Never summarised. */
  verbatim: string;
  logic: string;
  encoded: EncodedStep[];
  inputs: RuleInputSummary[];
  /** Where our encoding had to interpret an ambiguous text. */
  review_notes: string[];
  approval_status: "unsigned" | "provisional" | "certified";
  approved_by: string | null;
  approved_at: string | null;
  signature: string | null;
  signature_matches: boolean;
  computed_signature: string | null;
}

export interface PackRequest extends EvaluateRequest {
  caller_ref: string;
  language: string;
}

/**
 * The pack comes back as text, not JSON, so it does not go through `request`.
 *
 * The body posted is the *evaluation*, never a record: the backend recomputes
 * the verdict rather than trusting anything the browser assembled. That is what
 * makes the document worth carrying into a hearing.
 */
async function requestText(path: string, body: unknown): Promise<string> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("The service is not reachable right now.", 0);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((parsed: { detail?: unknown }) =>
        typeof parsed.detail === "string" ? parsed.detail : null,
      )
      .catch(() => null);
    throw new ApiError(detail ?? `Request failed (${response.status})`, response.status);
  }

  return await response.text();
}

export const api = {
  health: () => request<HealthResponse>("/healthz"),
  areas: () => request<AreasResponse>("/areas"),
  packLanguages: () => request<{ languages: string[] }>("/evidence-pack/languages"),
  evidencePack: (body: PackRequest) => requestText("/evidence-pack", body),
  evaluate: (body: EvaluateRequest) =>
    request<EvaluationRecord>("/evaluate", { method: "POST", body: JSON.stringify(body) }),
  provenance: () => request<ProvenanceListing>("/provenance"),
  // The id carries dots but no slashes, so it needs encoding for safety rather
  // than because any current rule requires it.
  provenanceDetail: (ruleId: string) =>
    request<ProvenanceDetail>(`/provenance/${encodeURIComponent(ruleId)}`),
};
