import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AVAILABLE_LANGUAGES,
  LANGUAGES,
  type LanguageCode,
  applyLanguage,
  isTranslated,
  storedLanguage,
} from ".";

/**
 * The language layer, tested below the switcher.
 *
 * The switcher currently offers one language, because one is all the interface
 * can render. That must not mean the RTL foundation stops being checked: Arabic
 * is coming, `dir="rtl"` mirrors the entire layout, and **RTL regressions are
 * silent** — nothing throws, the page is simply wrong, and nobody notices until
 * a demo (D-021).
 *
 * So these exercise `applyLanguage` directly. They keep working unchanged on the
 * day the Arabic button appears.
 */

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.dir = "ltr";
  document.documentElement.lang = "en";
  localStorage.clear();
});

describe("applying a language to the document", () => {
  it("mirrors the layout for Arabic", () => {
    applyLanguage("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
  });

  it("keeps Malayalam left-to-right", () => {
    // A different script is not a different direction. Treating RTL as "not
    // English" would mirror Malayalam too.
    applyLanguage("ml");
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("ml");
  });

  it("returns to left-to-right when English is chosen again", () => {
    applyLanguage("ar");
    applyLanguage("en");
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("sets a lang attribute the stylesheet can hang a font off", () => {
    // index.css selects html[lang="ar"] and html[lang="ml"] for their script
    // fonts. A missing or wrong `lang` silently drops the font stack.
    for (const code of Object.keys(LANGUAGES) as LanguageCode[]) {
      applyLanguage(code);
      expect(document.documentElement.lang).toBe(code);
    }
  });
});

describe("remembering a choice", () => {
  it("survives a reload", () => {
    applyLanguage("en");
    expect(storedLanguage()).toBe("en");
  });

  it("does not pin a reader to a language we have stopped rendering", () => {
    // A marker restored because a reviewer found a problem must not leave a
    // returning reader on the locale we just withdrew.
    applyLanguage("ar");
    expect(isTranslated("ar")).toBe(false);
    expect(storedLanguage()).toBeNull();
  });

  it("ignores a stored value that is not a language", () => {
    localStorage.setItem("bayyina.language", "klingon");
    expect(storedLanguage()).toBeNull();
  });

  it("survives a browser that refuses storage", () => {
    // Private windows and blocked site data make localStorage *throw*, not
    // return null. An unreadable preference must not take the page down.
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("access denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("access denied");
    });

    expect(storedLanguage()).toBeNull();
    expect(() => applyLanguage("en")).not.toThrow();
    expect(document.documentElement.lang).toBe("en");
  });
});

describe("what the switcher is allowed to offer", () => {
  it("offers exactly the languages that are translated", () => {
    expect(AVAILABLE_LANGUAGES).toEqual(
      (Object.keys(LANGUAGES) as LanguageCode[]).filter(isTranslated),
    );
  });

  it("never offers a language whose strings are still English", () => {
    // The defect this replaced: Arabic differed from English in 1 of 57 strings
    // and Malayalam in zero, so two of three buttons changed nothing on screen.
    for (const code of AVAILABLE_LANGUAGES) {
      expect(isTranslated(code), `${code} is offered but not translated`).toBe(true);
    }
  });

  it("always offers English, which is the source", () => {
    expect(AVAILABLE_LANGUAGES).toContain("en");
  });

  it("keeps every planned language listed, translated or not", () => {
    // LANGUAGES is the roadmap and the PDF templates and voice scripts read from
    // it. Deleting Arabic and Malayalam here to tidy the switcher would delete
    // the product's reason to exist — no phone channel in Dubai answers a
    // tenancy question in Malayalam, which is the point.
    expect(Object.keys(LANGUAGES).sort()).toEqual(["ar", "en", "ml"]);
  });
});
