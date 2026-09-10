import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Provenance from "./Provenance";

/**
 * The page exists so a reviewer can compare a published clause against our
 * encoding of it. These tests assert that both halves of that comparison reach
 * the screen, and that nothing on the page overstates what it is.
 */

const LISTING = {
  count: 2,
  rules: [
    {
      rule_id: "rent_increase.dubai.decree_43_2013",
      version: 1,
      title: "Decree No. (43) of 2013 Determining Increases in Real Property Rent",
      clause: "Article 1",
      approval_status: "provisional" as const,
      signature: "sha256:bc45809fff",
      signature_matches: true,
    },
    {
      rule_id: "notice_validity.dubai.law_26_2007_a14",
      version: 1,
      title: "Law No. (26) of 2007",
      clause: "Article 14",
      approval_status: "provisional" as const,
      signature: "sha256:4959418b04",
      signature_matches: true,
    },
  ],
};

const DETAIL = {
  rule_id: "rent_increase.dubai.decree_43_2013",
  version: 1,
  jurisdiction: "AE-DU",
  effective_from: "2013-12-09",
  effective_to: null,
  citation: {
    document_id: "dubai_decree_43_2013",
    title: "Decree No. (43) of 2013 Determining Increases in Real Property Rent",
    clause: "Article 1",
    url: "https://dubailand.gov.ae/",
  },
  verbatim:
    "The maximum rent increase for real property units in the Emirate of Dubai\nshall be determined as follows:\n\n1. no rent increase, where the rent is up to 10% less;",
  logic: "banded_percentage",
  encoded: [
    {
      step: 1,
      condition: "the rent is up to 10% below the market average, including exactly 10%",
      outcome: "no increase is permitted",
    },
    {
      step: 2,
      condition: "the rent is more than 10% and up to 20% below the market average",
      outcome: "the increase may not exceed 5% of the current rent",
    },
  ],
  inputs: [
    {
      name: "current_annual_rent",
      type: "money",
      currency: "AED",
      required: true,
      derived: false,
    },
    {
      name: "market_average_rent",
      type: "money",
      currency: "AED",
      required: true,
      derived: true,
    },
  ],
  review_notes: [
    "INTERPRETATION. The decree states its bands in whole percentages.",
    "TRANSLATION. The verbatim text recorded here is an unofficial English translation.",
  ],
  approval_status: "provisional" as const,
  approved_by: "Bayyina team",
  approved_at: "2026-09-09T08:00:29Z",
  signature: "sha256:bc45809fffe25406e2d032825cc3f60cbee8c003ddb5acc91b57c2f92c6400ab",
  signature_matches: true,
  computed_signature: null as string | null,
};

function respondWith(listing: unknown, detail: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/provenance/") ? detail : listing;
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
}

beforeEach(() => respondWith(LISTING, DETAIL));
afterEach(() => vi.unstubAllGlobals());

describe("Provenance", () => {
  it("lists every rule in the corpus", async () => {
    render(<Provenance />);

    expect(await screen.findByText(/Decree No\. \(43\) of 2013/)).toBeInTheDocument();
    expect(screen.getByText(/Law No\. \(26\) of 2007/)).toBeInTheDocument();
  });

  it("says on the list that nothing is reviewed yet", async () => {
    // A reader who sees a signature and an official citation will assume a
    // lawyer signed this off. Nobody has, and the page must not let that stand.
    render(<Provenance />);

    const pending = await screen.findAllByText(/Pending review by a qualified lawyer/);
    expect(pending).toHaveLength(2);
  });

  it("shows the published text and our encoding together", async () => {
    // The comparison is the whole point of the page.
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    expect(await screen.findByText(/What the published text says/)).toBeInTheDocument();
    expect(screen.getByText(/What we encoded/)).toBeInTheDocument();
    expect(screen.getByText(/no rent increase, where the rent is up to 10% less/)).
      toBeInTheDocument();
    expect(screen.getByText(/no increase is permitted/)).toBeInTheDocument();
  });

  it("renders one step per encoded band", async () => {
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    const steps = await screen.findAllByText(/^(If|Then)$/);
    // Two bands, each with a condition and an outcome.
    expect(steps).toHaveLength(4);
  });

  it("marks which inputs we work out ourselves", async () => {
    // The market average is ours, not the RERA index. A reviewer asks this
    // first, so the page answers it without being asked.
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    expect(
      await screen.findByText(/We work this out from registered contracts/),
    ).toBeInTheDocument();
    expect(screen.getByText(/You tell us this/)).toBeInTheDocument();
  });

  it("publishes the notes about where we interpreted", async () => {
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    expect(await screen.findByText(/INTERPRETATION\./)).toBeInTheDocument();
    expect(screen.getByText(/TRANSLATION\./)).toBeInTheDocument();
  });

  it("shows the signature and says it matches", async () => {
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    expect(await screen.findByText(new RegExp(DETAIL.signature))).toBeInTheDocument();
    expect(
      screen.getByText(/The signature matches the rule we are running/),
    ).toBeInTheDocument();
  });

  it("raises an alert when the signature does not match", async () => {
    // Should be unreachable: the corpus is verified at boot and in CI. Tested
    // because the one thing this page must never do is present a forgery as
    // provenance.
    respondWith(LISTING, {
      ...DETAIL,
      signature_matches: false,
      computed_signature: "sha256:0000000000",
    });
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/does not match/);
    expect(screen.getByText(/sha256:0000000000/)).toBeInTheDocument();
  });

  it("returns to the list without reloading the page", async () => {
    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);
    await screen.findByText(/What we encoded/);

    await userEvent.click(screen.getByRole("button", { name: /All rules/ }));

    await waitFor(() =>
      expect(screen.getByText(/Law No\. \(26\) of 2007/)).toBeInTheDocument(),
    );
  });

  it("never shows one rule's clause under another rule's heading", async () => {
    // The failure this guards: open rule 1, go back, open rule 2, and the
    // second rule's heading renders above the first rule's text while the
    // fetch is in flight. A provenance page showing the wrong provenance is
    // the one failure this page cannot have, and it is invisible in a fast
    // test unless the second response is deliberately withheld.
    // A holder rather than a bare `let`: TypeScript's control-flow analysis
    // does not see the assignment inside the promise executor, narrows the
    // variable to `null`, and then rejects calling it.
    const gate: { release?: () => void } = {};
    let detailCalls = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (!url.includes("/provenance/")) {
          return new Response(JSON.stringify(LISTING), { status: 200 });
        }
        detailCalls += 1;
        if (detailCalls === 2) {
          await new Promise<void>((resolve) => {
            gate.release = resolve;
          });
          return new Response(
            JSON.stringify({
              ...DETAIL,
              rule_id: "notice_validity.dubai.law_26_2007_a14",
              verbatim: "Ninety days notice, in writing.",
              citation: { ...DETAIL.citation, title: "Law No. (26) of 2007" },
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify(DETAIL), { status: 200 });
      }),
    );

    render(<Provenance />);
    await userEvent.click((await screen.findAllByRole("button"))[0]);
    await screen.findByText(/no rent increase, where the rent is up to 10% less/);

    await userEvent.click(screen.getByRole("button", { name: /All rules/ }));
    const openButtons = await screen.findAllByRole("button", {
      name: /Check this encoding/,
    });
    await userEvent.click(openButtons[1]);

    // The second rule's detail has not arrived. The first rule's text must not
    // be on screen regardless.
    expect(
      screen.queryByText(/no rent increase, where the rent is up to 10% less/),
    ).not.toBeInTheDocument();

    gate.release?.();
    expect(await screen.findByText(/Ninety days notice, in writing/)).toBeInTheDocument();
  });

  it("says the service is unreachable rather than showing an empty page", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    render(<Provenance />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/not reachable/);
  });
});
