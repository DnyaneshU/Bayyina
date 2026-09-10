import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Checker from "./Checker";

/**
 * The checker is the first thing a stranger touches, so these tests are written
 * from the reader's side: what did they type, and what did they end up believing?
 *
 * The three cases the plan calls for — permitted, not permitted, and the
 * one-dirham-over edge — are asserted against the real numbers the backend
 * returns, so the boundary is checked here and not only in Python.
 */

const CITATION = {
  document_id: "dubai_decree_43_2013",
  title: "Decree No. (43) of 2013 Determining Increases in Real Property Rent",
  clause: "Article 1",
  url: "https://dubailand.gov.ae/",
  verbatim: "The maximum rent increase for real property units shall be determined as follows…",
};

function record(overrides: Record<string, unknown> = {}) {
  return {
    eval_id: "ev_test",
    rule_id: "rent_increase.dubai.decree_43_2013",
    rule_version: 1,
    rule_signature: "sha256:bc45809fffe25406e2d032825cc3f60cbee8c003ddb5acc91b57c2f92c6400ab",
    review_status: "provisional",
    state: "CLEAR_WITH_CONDITIONS",
    verdict: "not_permitted",
    inputs: {},
    input_sources: {},
    computed: {
      gap_pct: 0.08046,
      band_matched: 0,
      max_increase_pct: 0.0,
      max_lawful_rent: "80000.00",
      proposed_increase_pct: 0.2,
    },
    citation: CITATION,
    evidence: { contract_count: null, snapshot_id: "user_supplied" },
    conditions: ["market_average_not_derived"],
    confidence: null,
    created_at: "2026-09-09T08:00:00Z",
    ...overrides,
  };
}

function mockEvaluate(body: Record<string, unknown>, ok = true, status = 200) {
  // Routed by URL. The checker asks `/areas` on mount to find out whether it can
  // derive a market average at all; answering that with an evaluation record
  // would put the form into derive mode and remove the field these tests fill
  // in. 503 is the honest answer here and the one the published image gives,
  // since the comparables database is optional at boot (D-074).
  const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    if (String(input).includes("/areas")) {
      return Promise.resolve({
        ok: false,
        status: 503,
        json: async () => ({ detail: "no market data" }),
      });
    }
    return Promise.resolve({ ok, status, json: async () => body });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The body of the POST to /evaluate, whichever call that turned out to be. */
function evaluateBody(fetchMock: ReturnType<typeof mockEvaluate>) {
  const call = fetchMock.mock.calls.find(
    ([url]) => String(url).includes("/evaluate"),
  );
  if (!call) throw new Error("no call to /evaluate was made");
  return JSON.parse(call[1]?.body as string);
}

/** Did the checker actually ask the backend to evaluate anything? */
function evaluated(fetchMock: ReturnType<typeof mockEvaluate>) {
  return fetchMock.mock.calls.some(([url]) => String(url).includes("/evaluate"));
}

async function fillAndSubmit(
  user: ReturnType<typeof userEvent.setup>,
  current: string,
  proposed: string,
  market: string,
) {
  await user.type(screen.getByLabelText(/what you pay now/i), current);
  await user.type(screen.getByLabelText(/what they are asking for/i), proposed);
  await user.type(screen.getByLabelText(/market average/i), market);
  await user.click(screen.getByRole("button", { name: /check this increase/i }));
}

afterEach(() => vi.restoreAllMocks());

describe("Checker", () => {
  it("asks for the three amounts and says where the market average comes from", () => {
    render(<Checker />);
    expect(screen.getByLabelText(/what you pay now/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/what they are asking for/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/market average/i)).toBeInTheDocument();
    expect(screen.getByText(/automatic comparables arrive/i)).toBeInTheDocument();
  });

  // --- The three cases the plan asks to be verified by hand -------------------

  it("case 1 — not permitted: says so and shows the ceiling", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /above the published limit/i })).toBeVisible(),
    );
    expect(screen.getByText("AED 80,000")).toBeInTheDocument();
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("case 2 — permitted: the rule says yes as readily as it says no", async () => {
    mockEvaluate(
      record({
        verdict: "permitted",
        computed: {
          gap_pct: 0.25,
          band_matched: 2,
          max_increase_pct: 0.1,
          max_lawful_rent: "88000.00",
          proposed_increase_pct: 0.05,
        },
      }),
    );
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "84000", "106667");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /within the published limit/i })).toBeVisible(),
    );
    expect(screen.getByText("AED 88,000")).toBeInTheDocument();
  });

  it("case 3 — one dirham over the ceiling is not permitted", async () => {
    // The edge that matters. AED 88,000.01 against a ceiling of AED 88,000.
    mockEvaluate(
      record({
        verdict: "not_permitted",
        computed: {
          gap_pct: 0.25,
          band_matched: 2,
          max_increase_pct: 0.1,
          max_lawful_rent: "88000.00",
          proposed_increase_pct: 0.1000001,
        },
      }),
    );
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "88000.01", "106667");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /above the published limit/i })).toBeVisible(),
    );
  });

  // --- The condition must be named -------------------------------------------

  it("names the condition when the market average came from the reader", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByText(/rests on one thing/i)).toBeVisible());
    expect(screen.getByText(/you gave us the market average/i)).toBeInTheDocument();
  });

  it("never claims we derived a figure the reader supplied", async () => {
    const fetchMock = mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = evaluateBody(fetchMock);

    // Inventing a contract count to obtain a clean CLEAR would be fabricating
    // evidence. The request must not carry one.
    expect(body.market.contract_count).toBeUndefined();
    expect(body.input_sources.market_average_rent).toBe("user_supplied");
  });

  it("sends amounts as strings, never as JSON numbers", async () => {
    const fetchMock = mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = evaluateBody(fetchMock);
    for (const value of Object.values(body.inputs)) {
      expect(typeof value).toBe("string");
    }
  });

  // --- Human review is an outcome, not an error ------------------------------

  it("renders human review as considered, never as a failure", async () => {
    mockEvaluate(
      record({
        state: "HUMAN_REVIEW_REQUIRED",
        verdict: null,
        computed: {},
        conditions: [],
        confidence: null,
        evidence: { contract_count: 4, snapshot_id: "2026-Q3" },
      }),
    );
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /needs a person/i })).toBeVisible(),
    );

    // Not an error: no alert role, no danger colour, and the words the glossary
    // bans for this state do not appear.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/needs a person to look at this/i)).toHaveStyle({
      color: "var(--color-review)",
    });
    expect(document.body.textContent).not.toMatch(/error|failed|unavailable/i);
  });

  it("quotes no figure at all when the data is too thin", async () => {
    // The payload deliberately carries computed figures, which the backend's
    // record type makes impossible. The interface is the last surface before a
    // person reads a number, so it must not print one it was told not to have -
    // even if something upstream regresses.
    mockEvaluate(
      record({
        state: "HUMAN_REVIEW_REQUIRED",
        verdict: null,
        computed: {
          gap_pct: 0.08046,
          band_matched: 0,
          max_increase_pct: 0.0,
          max_lawful_rent: "80000.00",
          proposed_increase_pct: 0.2,
        },
        conditions: [],
        confidence: null,
        evidence: { contract_count: 4, snapshot_id: "2026-Q3" },
      }),
    );
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /needs a person/i })).toBeVisible(),
    );
    // G5: the ceiling, the gap and the permitted percentage must all be absent.
    expect(screen.queryByText(/AED 80,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("still shows the rule when it cannot answer", async () => {
    mockEvaluate(
      record({
        state: "HUMAN_REVIEW_REQUIRED",
        verdict: null,
        computed: {},
        conditions: [],
        confidence: null,
        evidence: { contract_count: 4, snapshot_id: "2026-Q3" },
      }),
    );
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByText("Article 1")).toBeInTheDocument());
  });

  // --- Provenance ------------------------------------------------------------

  it("always shows the clause, its version and its signature", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByText("Article 1")).toBeInTheDocument());
    expect(screen.getByText(/sha256:bc45809/)).toBeInTheDocument();
  });

  it("shows the verbatim clause on request", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByRole("button", { name: /show the clause/i })).toBeVisible());
    await user.click(screen.getByRole("button", { name: /show the clause/i }));
    expect(screen.getByText(/maximum rent increase for real property units/i)).toBeVisible();
  });

  it("discloses that the encoding is pending review, on every result", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    // D4 attaches to the verdict, not the greeting (docs/GLOSSARY.md).
    await waitFor(() =>
      expect(screen.getByText(/pending review by a qualified lawyer/i)).toBeVisible(),
    );
  });

  // --- Input handling --------------------------------------------------------

  it("does not call the backend when a field is empty", async () => {
    const fetchMock = mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await user.click(screen.getByRole("button", { name: /check this increase/i }));

    expect(evaluated(fetchMock)).toBe(false);
    expect(screen.getAllByRole("alert").length).toBe(3);
  });

  it("explains what a valid amount looks like", async () => {
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "eighty thousand", "96000", "87000");

    expect(screen.getByText(/in numbers, like 80000/i)).toBeInTheDocument();
  });

  it("rejects a zero amount", async () => {
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "0", "96000", "87000");

    expect(screen.getByText(/greater than zero/i)).toBeInTheDocument();
  });

  it("ties each error to its field for screen readers", async () => {
    const user = userEvent.setup();
    render(<Checker />);
    await user.click(screen.getByRole("button", { name: /check this increase/i }));

    const field = screen.getByLabelText(/what you pay now/i);
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAttribute("aria-describedby", "current_annual_rent-error");
  });

  it("surfaces the reason the backend refused, not just a status code", async () => {
    mockEvaluate({ detail: "current_annual_rent must be positive" }, false, 422);
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() =>
      expect(screen.getByText(/current_annual_rent must be positive/i)).toBeInTheDocument(),
    );
  });

  it("degrades gracefully when the service is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByText(/not reachable/i)).toBeInTheDocument());
  });

  it("lets the reader check another increase", async () => {
    mockEvaluate(record());
    const user = userEvent.setup();
    render(<Checker />);
    await fillAndSubmit(user, "80000", "96000", "87000");

    await waitFor(() => expect(screen.getByText(/above the published limit/i)).toBeVisible());
    await user.click(screen.getByRole("button", { name: /check another increase/i }));

    expect(screen.getByLabelText(/what you pay now/i)).toHaveValue("");
  });
});
