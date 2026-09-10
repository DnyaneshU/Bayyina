import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.dir = "ltr";
  document.documentElement.lang = "en";
  // The choice now persists, so it must not leak between tests.
  localStorage.clear();
});

function mockHealth(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        checks: {
          corpus_loaded: true,
          corpus_signed: true,
          audit_writable: true,
        },
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
    expect(
      screen.getByRole("heading", { name: /bayyina/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not legal advice/i)).toBeInTheDocument();
  });

  it("says nothing about the backend while it is healthy", async () => {
    // A green panel on every load is noise. The absence of a warning is the
    // signal, so the checker is what the reader sees.
    mockHealth();
    render(<App />);
    await waitFor(() =>
      expect(screen.getByLabelText(/what you pay now/i)).toBeInTheDocument(),
    );
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
    await waitFor(() =>
      expect(screen.getByText(/not reachable/i)).toBeInTheDocument(),
    );
  });

  it("offers no language switcher while the interface speaks one language", () => {
    // A control with one option is not a choice, and Arabic and Malayalam are
    // not yet translated. See src/i18n/language.test.ts for the layer that keeps
    // the RTL foundation exercised in the meantime.
    mockHealth();
    render(<App />);
    expect(
      screen.queryByRole("navigation", { name: /language/i }),
    ).not.toBeInTheDocument();
  });

  it("shows nothing apologising for the languages it does not have", () => {
    // An earlier fix explained the dead buttons instead of removing them. A
    // caption on a broken control is still a broken control.
    mockHealth();
    render(<App />);
    expect(screen.queryByText(/not available in/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/machine-translated/i)).not.toBeInTheDocument();
  });
});

describe("App, once a second language is translated", () => {
  // Proves the claim the derivation makes: filling in a locale file and removing
  // its marker is the whole of the work. No component changes, no list to edit.
  beforeEach(() => {
    vi.resetModules();
  });

  it("shows the switcher, with one button per available language", async () => {
    vi.doMock("./i18n", async (importOriginal) => {
      const actual = await importOriginal<typeof import("./i18n")>();
      return { ...actual, AVAILABLE_LANGUAGES: ["en", "ar"] };
    });
    const { default: AppWithArabic } = await import("./App");

    mockHealth();
    render(<AppWithArabic />);

    const nav = screen.getByRole("navigation", { name: /language/i });
    expect(
      within(nav).getByRole("button", { name: "English" }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("button", { name: "العربية" }),
    ).toBeInTheDocument();
    expect(
      within(nav).queryByRole("button", { name: "മലയാളം" }),
    ).not.toBeInTheDocument();
  });

  it("switching to Arabic mirrors the page", async () => {
    vi.doMock("./i18n", async (importOriginal) => {
      const actual = await importOriginal<typeof import("./i18n")>();
      return { ...actual, AVAILABLE_LANGUAGES: ["en", "ar"] };
    });
    const { default: AppWithArabic } = await import("./App");

    mockHealth();
    const user = userEvent.setup();
    render(<AppWithArabic />);

    expect(document.documentElement.dir).toBe("ltr");
    await user.click(screen.getByRole("button", { name: "العربية" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
  });
});
