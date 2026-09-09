import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.dir = "ltr";
  document.documentElement.lang = "en";
});

function mockHealth(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        checks: { corpus_loaded: true, corpus_signed: true, audit_writable: true },
        not_yet_checked: ["market_snapshot"],
        corpus_signed: true,
        rule_count: 2,
        rules: [],
        ...overrides,
      }),
    }),
  );
}

describe("App", () => {
  it("renders the product name and the not-advice disclosure", async () => {
    mockHealth();
    render(<App />);
    expect(screen.getByRole("heading", { name: /bayyina/i })).toBeInTheDocument();
    expect(screen.getByText(/not legal advice/i)).toBeInTheDocument();
  });

  it("says nothing about the backend while it is healthy", async () => {
    // A green panel on every load is noise. The absence of a warning is the
    // signal, so the checker is what the reader sees.
    mockHealth();
    render(<App />);
    await waitFor(() => expect(screen.getByLabelText(/what you pay now/i)).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("warns when the corpus is not signed", async () => {
    // G7 means this should be unreachable - the service cannot boot. If it ever
    // is reachable, a reader deserves to know before trusting a number.
    mockHealth({ corpus_signed: false });
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("degrades gracefully when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/not reachable/i)).toBeInTheDocument());
  });

  it("switching to Arabic sets dir=rtl on the document", async () => {
    // RTL is a layout concern, not a font swap. If this regresses, the Arabic
    // layout silently stops mirroring and nobody notices until a demo.
    mockHealth();
    const user = userEvent.setup();
    render(<App />);

    expect(document.documentElement.dir).toBe("ltr");
    await user.click(screen.getByRole("button", { name: "العربية" }));

    await waitFor(() => {
      expect(document.documentElement.dir).toBe("rtl");
      expect(document.documentElement.lang).toBe("ar");
    });
  });

  it("switching to Malayalam stays left-to-right", async () => {
    mockHealth();
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "മലയാളം" }));

    await waitFor(() => {
      expect(document.documentElement.lang).toBe("ml");
      expect(document.documentElement.dir).toBe("ltr");
    });
  });
});
