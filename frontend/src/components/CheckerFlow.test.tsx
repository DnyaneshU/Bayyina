import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Checker from "./Checker";

/**
 * The full Mode A journey: property details in, a derived comparable, a verdict,
 * and a document to take away.
 *
 * The existing Checker tests cover the manual path, where the reader supplies
 * the market average. These cover the path where we work it out — and the path
 * where we cannot, which is what the published image actually does.
 */

const AREAS = {
  snapshot_id: "2026-Q3",
  count: 3,
  areas: ["Al Barsha First", "Al Barsha South Third", "Jumeirah First"],
};

function record(overrides: Record<string, unknown> = {}) {
  return {
    eval_id: "ev_2b7c",
    rule_id: "rent_increase.dubai.decree_43_2013",
    rule_version: 1,
    rule_signature: "sha256:bc45809fffe25406e2d032825cc3f60cbee8c003ddb5acc91b57c2f92c6400ab",
    review_status: "provisional",
    state: "CLEAR",
    verdict: "not_permitted",
    inputs: {
      current_annual_rent: "80000",
      proposed_annual_rent: "96000",
      market_average_rent: "87000",
    },
    input_sources: {
      current_annual_rent: "caller_stated",
      proposed_annual_rent: "caller_stated",
      market_average_rent: "dld_open_rent_contracts_derived",
    },
    computed: {
      gap_pct: 0.0805,
      max_increase_pct: 0,
      max_lawful_rent: "80000.00",
      proposed_increase_pct: 0.2,
      band_matched: 0,
    },
    citation: {
      document_id: "dubai_decree_43_2013",
      title: "Decree No. (43) of 2013",
      clause: "Article 1",
      url: "https://dubailand.gov.ae/",
      verbatim: "The maximum rent increase...",
    },
    evidence: { contract_count: 5019, snapshot_id: "2026-Q3" },
    conditions: [],
    confidence: null,
    created_at: "2026-09-10T08:00:00Z",
    ...overrides,
  };
}

/** A fetch Response, as much of one as the client actually touches. */
function fakeResponse(
  ok: boolean,
  status: number,
  json: unknown,
  text = "",
): Promise<Response> {
  return Promise.resolve({
    ok,
    status,
    json: async () => json,
    text: async () => text,
  } as unknown as Response);
}

interface Routes {
  areasOk?: boolean;
  packText?: string;
  packOk?: boolean;
}

function mockBackend({ areasOk = true, packText = "PACK", packOk = true }: Routes = {}) {
  const calls: Array<{ url: string; body?: unknown }> = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(init.body as string) : undefined });

    if (url.includes("/areas")) {
      return areasOk
        ? fakeResponse(true, 200, AREAS)
        : fakeResponse(false, 503, { detail: "no market data" });
    }
    if (url.includes("/evidence-pack")) {
      return fakeResponse(
        packOk,
        packOk ? 200 : 422,
        { detail: "no template" },
        packText,
      );
    }
    return fakeResponse(true, 200, record());
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}

/** jsdom implements neither of these; the component only needs them to exist. */
function stubDownloads() {
  const created: string[] = [];
  const target = URL as unknown as Record<string, unknown>;
  target.createObjectURL = () => {
    created.push("blob:x");
    return "blob:x";
  };
  target.revokeObjectURL = () => undefined;
  return created;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the checker, when we can derive a market average", () => {
  it("offers to work the figure out and asks for the property instead", async () => {
    mockBackend();
    render(<Checker />);

    expect(
      await screen.findByLabelText(/work it out from registered contracts/i),
    ).toBeChecked();
    expect(screen.getByLabelText(/^area$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^bedrooms$/i)).toBeInTheDocument();
    // The reader is not asked for a number we are about to look up ourselves.
    expect(screen.queryByLabelText(/market average/i)).not.toBeInTheDocument();
  });

  it("sends the dwelling, and never a market figure alongside it", async () => {
    // Sending both is refused by the backend, because nobody could tell which
    // number the answer used.
    const { calls } = mockBackend();
    const user = userEvent.setup();
    render(<Checker />);

    await screen.findByLabelText(/^area$/i);
    await user.type(screen.getByLabelText(/^area$/i), "Al Barsha First");
    await user.type(screen.getByLabelText(/^bedrooms$/i), "2");
    await user.type(screen.getByLabelText(/what you pay now/i), "80000");
    await user.type(screen.getByLabelText(/what they are asking for/i), "96000");
    await user.click(screen.getByRole("button", { name: /check this increase/i }));

    await waitFor(() =>
      expect(calls.some((call) => call.url.includes("/evaluate"))).toBe(true),
    );
    const sent = calls.find((call) => call.url.includes("/evaluate"))?.body as {
      dwelling?: { area: string; kind: string; bedrooms: number };
      inputs: Record<string, string>;
    };

    expect(sent.dwelling).toEqual({
      area: "Al Barsha First",
      kind: "flat",
      bedrooms: 2,
    });
    expect(sent.inputs.market_average_rent).toBeUndefined();
  });

  it("offers the known areas rather than making the reader guess a spelling", async () => {
    mockBackend();
    render(<Checker />);

    await screen.findByLabelText(/^area$/i);
    const options = document.querySelectorAll("#area-options option");
    expect([...options].map((option) => option.getAttribute("value"))).toEqual(
      AREAS.areas,
    );
  });

  it("will not submit a property with no area", async () => {
    const { calls } = mockBackend();
    const user = userEvent.setup();
    render(<Checker />);

    await screen.findByLabelText(/^area$/i);
    await user.type(screen.getByLabelText(/^bedrooms$/i), "2");
    await user.type(screen.getByLabelText(/what you pay now/i), "80000");
    await user.type(screen.getByLabelText(/what they are asking for/i), "96000");
    await user.click(screen.getByRole("button", { name: /check this increase/i }));

    expect(await screen.findByText(/pick an area from the list/i)).toBeInTheDocument();
    expect(calls.some((call) => call.url.includes("/evaluate"))).toBe(false);
  });

  it("lets the reader supply the figure instead", async () => {
    mockBackend();
    const user = userEvent.setup();
    render(<Checker />);

    await user.click(await screen.findByLabelText(/i already have the figure/i));

    expect(screen.getByLabelText(/market average/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^area$/i)).not.toBeInTheDocument();
  });
});

describe("the checker, when the market data is absent", () => {
  it("says so plainly and leaves the rest working", async () => {
    // This is what the published image does: the comparables database is
    // gitignored and optional at boot, so /areas answers 503. That is a
    // supported state, not a fault.
    mockBackend({ areasOk: false });
    render(<Checker />);

    expect(
      await screen.findByText(/cannot work out market averages right now/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/market average/i)).toBeInTheDocument();
  });

  it("offers no control that cannot work", async () => {
    mockBackend({ areasOk: false });
    render(<Checker />);

    await screen.findByText(/cannot work out market averages right now/i);
    expect(
      screen.queryByLabelText(/work it out from registered contracts/i),
    ).not.toBeInTheDocument();
  });

  it("never calls the absence an error", async () => {
    mockBackend({ areasOk: false });
    render(<Checker />);

    const notice = await screen.findByText(/cannot work out market averages right now/i);
    expect(notice.textContent).not.toMatch(/\b(error|failed|failure|sorry)\b/i);
  });
});

describe("the document a reader takes away", () => {
  async function reachResult(user: ReturnType<typeof userEvent.setup>) {
    render(<Checker />);
    await screen.findByLabelText(/^area$/i);
    await user.type(screen.getByLabelText(/^area$/i), "Al Barsha First");
    await user.type(screen.getByLabelText(/^bedrooms$/i), "2");
    await user.type(screen.getByLabelText(/what you pay now/i), "80000");
    await user.type(screen.getByLabelText(/what they are asking for/i), "96000");
    await user.click(screen.getByRole("button", { name: /check this increase/i }));
    await screen.findByRole("button", { name: /download my case report/i });
  }

  it("is offered once there is a result", async () => {
    mockBackend();
    stubDownloads();
    await reachResult(userEvent.setup());

    expect(
      screen.getByRole("button", { name: /download my case report/i }),
    ).toBeInTheDocument();
  });

  it("posts the evaluation, never the verdict", async () => {
    // The backend recomputes rather than trusting anything this browser
    // assembled. A record posted over HTTP would be a verdict nobody computed,
    // carrying our citation and our name (G10).
    const { calls } = mockBackend();
    stubDownloads();
    const user = userEvent.setup();
    await reachResult(user);

    await user.click(screen.getByRole("button", { name: /download my case report/i }));

    await waitFor(() =>
      expect(calls.some((call) => call.url.includes("/evidence-pack"))).toBe(true),
    );
    const sent = calls.find((call) => call.url.includes("/evidence-pack"))
      ?.body as Record<string, unknown>;

    expect(sent.dwelling).toBeDefined();
    expect(sent.caller_ref).toBe("ev_2b7c");
    expect(sent.language).toBeDefined();
    expect(sent.state).toBeUndefined();
    expect(sent.verdict).toBeUndefined();
    expect(sent.computed).toBeUndefined();
  });

  it("hands the reader a file", async () => {
    mockBackend({ packText: "BAYYINA — YOUR CASE REPORT" });
    const created = stubDownloads();
    const user = userEvent.setup();
    await reachResult(user);

    await user.click(screen.getByRole("button", { name: /download my case report/i }));

    await waitFor(() => expect(created).toHaveLength(1));
  });

  it("keeps the answer on screen when the download fails", async () => {
    // Losing the document must not look like losing the answer.
    mockBackend({ packOk: false });
    stubDownloads();
    const user = userEvent.setup();
    await reachResult(user);

    await user.click(screen.getByRole("button", { name: /download my case report/i }));

    expect(await screen.findByText(/could not prepare that report/i)).toBeInTheDocument();
    expect(screen.getByText(/above the published limit/i)).toBeInTheDocument();
  });

  it("is offered even when we could not answer", async () => {
    // The pack for a HUMAN_REVIEW_REQUIRED outcome names which facts were
    // missing and which rule would have applied. It is the one a person takes
    // to the Rental Dispute Centre when we could not help.
    const { fetchMock } = mockBackend();
    stubDownloads();
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/areas")) return fakeResponse(true, 200, AREAS);
      if (url.includes("/evidence-pack")) return fakeResponse(true, 200, {}, "PACK");
      return fakeResponse(
        true,
        200,
        record({ state: "HUMAN_REVIEW_REQUIRED", verdict: null, computed: {} }),
      );
    });

    await reachResult(userEvent.setup());

    expect(
      screen.getByRole("button", { name: /download my case report/i }),
    ).toBeInTheDocument();
  });
});
