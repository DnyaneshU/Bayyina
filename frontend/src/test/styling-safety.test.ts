import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { beforeAll, describe, expect, it } from "vitest";

/**
 * Styling that silently does nothing.
 *
 * `bg-[--color-ink-900]` is Tailwind v3 syntax. Under v4 it emits **no CSS at
 * all** — no error, no warning, just an element with no background. The submit
 * button shipped as white text on a white background and was invisible, and
 * every test still passed, because nothing in a jsdom test asserts that a class
 * produced a rule.
 *
 * v4 generates utilities from `@theme` variables instead: `--color-ink-900`
 * becomes `bg-ink-900`, `text-ink-900`, `border-ink-900`. That is the only form
 * allowed here.
 */

const SRC = join(__dirname, "..");
const ROOT = join(SRC, "..");

/**
 * A production build, run once for the whole file.
 *
 * Six tests below read the built stylesheet, and each used to build it itself
 * when `dist/` was missing. Under Vitest's default 5 s timeout that is a coin
 * toss: a cold `vite build` takes about a second on a developer's machine and
 * **7 s on a single core**, which is what a CI runner gives you. The build is
 * not slow because anything is wrong - it compiles Tailwind and subsets six
 * font faces. So it gets a hook with a timeout that reflects what it actually
 * costs, and the tests reading its output keep the ordinary one.
 *
 * Source is not the artifact. Everything checked below is present in
 * `index.css` and could still be absent from what ships - a dropped
 * `@font-face` or a mangled attribute selector fails silently, which is the
 * whole reason D-021 exists.
 *
 * The minifier rewrites `html[dir="rtl"]` to `html[dir=rtl]`, so the tests
 * match the built form rather than the authored one.
 */
const BUILD_TIMEOUT_MS = 180_000;

let cachedCss: string | null = null;

function ensureBuilt(): void {
  if (!existsSync(join(ROOT, "dist", "assets"))) {
    execSync("npm run build", { cwd: ROOT, stdio: "ignore" });
  }
}

function builtCss(): string {
  if (cachedCss === null) {
    ensureBuilt();
    cachedCss = readdirSync(join(ROOT, "dist", "assets"))
      .filter((file) => file.endsWith(".css"))
      .map((file) => readFileSync(join(ROOT, "dist", "assets", file), "utf8"))
      .join("\n");
  }
  return cachedCss;
}

beforeAll(ensureBuilt, BUILD_TIMEOUT_MS);

/** The v3 form: a bracketed CSS variable. Silently inert under v4. */
const V3_ARBITRARY_VARIABLE =
  /\b(bg|text|border|border-s|border-e|fill|stroke|outline|ring|from|via|to)-\[--/;

function walk(dir: string, extensions: string[]): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full, extensions);
    return extensions.some((ext) => entry.endsWith(ext)) ? [full] : [];
  });
}

describe("styling safety", () => {
  it("uses no Tailwind v3 arbitrary-variable classes", () => {
    const offenders: string[] = [];

    for (const file of walk(SRC, [".tsx", ".ts"])) {
      if (file.includes("styling-safety")) continue;
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, index) => {
          if (V3_ARBITRARY_VARIABLE.test(line)) {
            offenders.push(
              `${relative(SRC, file)}:${index + 1} — ${line.trim()}`,
            );
          }
        });
    }

    expect(
      offenders,
      `These emit no CSS under Tailwind v4. Use the theme utility (bg-ink-900), ` +
        `not the bracketed variable:\n  ${offenders.join("\n  ")}`,
    ).toEqual([]);
  });

  it("emits a real rule for every colour utility the interface uses", () => {
    // The only check that would have caught the invisible button: build, then
    // read the CSS and confirm the class actually exists in it.
    const css = builtCss();

    const used = new Set<string>();
    for (const file of walk(SRC, [".tsx"])) {
      if (file.includes(".test.")) continue;
      for (const match of readFileSync(file, "utf8").matchAll(
        /\b((?:bg|text|border)-(?:ink|paper|paper-raised|rule|clear|conditional|review|danger)[a-z0-9-]*)/g,
      )) {
        used.add(match[1]);
      }
    }

    expect(
      used.size,
      "no themed utilities found — has the markup changed?",
    ).toBeGreaterThan(4);

    const missing = [...used].filter((cls) => !css.includes(`.${cls}{`));
    expect(
      missing,
      `Used in markup but absent from the built CSS, so they do nothing:\n  ${missing.join("\n  ")}`,
    ).toEqual([]);
  });

  it("keeps the outcome colours defined as theme tokens", () => {
    // These are applied inline via style={}, so they must exist as real CSS
    // variables rather than as generated utilities.
    const css = readFileSync(join(SRC, "index.css"), "utf8");
    for (const token of [
      "--color-clear",
      "--color-conditional",
      "--color-review",
    ]) {
      expect(css, `${token} is missing from the theme`).toContain(`${token}:`);
    }
  });
});

describe("the design system survives the build", () => {

  it("still mirrors the layout for RTL", () => {
    // Without this rule Arabic renders left to right and nothing throws.
    const css = builtCss().replace(/["']/g, "");
    expect(css, "the RTL selector is gone from the built stylesheet").toContain(
      "html[dir=rtl]",
    );
    expect(css).toContain("direction:rtl");
  });

  it("still selects a face per script", () => {
    // Plain string containment, not a regex. Three attempts at a regex here
    // were mangled by escaping before reaching the file, and a test that cannot
    // be written correctly is a test nobody will maintain correctly.
    //
    // The minifier drops the quotes: `html[lang="ar"]` ships as `html[lang=ar]`.
    const css = builtCss().replace(/["']/g, "");

    for (const [lang, family] of [
      ["ar", "--font-arabic"],
      ["ml", "--font-malayalam"],
    ]) {
      expect(css, `html[lang=${lang}] lost its selector`).toContain(
        `html[lang=${lang}]`,
      );
      expect(css, `${family} is not applied to any script`).toContain(family);
    }
  });

  it("bundles all three scripts rather than fetching them", () => {
    const css = builtCss();
    for (const family of [
      "Noto Sans",
      "Noto Sans Arabic",
      "Noto Sans Malayalam",
    ]) {
      expect(css, `${family} is not declared`).toContain(family);
    }
    // A @font-face pointing at a third party would be a privacy leak on a page
    // about someone's tenancy, and would break under the strict CSP.
    expect(css, "a font is being fetched from a third party").not.toMatch(
      /@font-face[^}]*url\(\s*["']?https?:/,
    );

    const fonts = readdirSync(join(ROOT, "dist", "assets")).filter((f) =>
      f.endsWith(".woff2"),
    );
    expect(fonts.length, "no woff2 files were emitted").toBeGreaterThanOrEqual(
      6,
    );
    for (const script of ["latin", "arabic", "malayalam"]) {
      expect(
        fonts.some((f) => f.includes(script)),
        `no ${script} subset was bundled`,
      ).toBe(true);
    }
  });

  it("keeps money aligned", () => {
    // A column of rents whose digits do not line up is harder to compare, and
    // comparing them is the entire task.
    expect(builtCss()).toMatch(/font-variant-numeric:\s*tabular-nums/);
  });
});

describe("what ships is only what the markup asked for", () => {
  it("emits no Tailwind v3 arbitrary-variable utilities", () => {
    /**
     * These produce an invalid declaration — `background-color:--color-ink-900`
     * with no `var()` — so they do nothing, which is the defect D-058 was about.
     *
     * The one found in the build came from no component. It came from *this
     * file*: Tailwind v4 scans every project file for class names, and the test
     * documenting the banned syntax was teaching Tailwind to emit it. A test
     * fixture must not be able to add a rule to the production stylesheet.
     *
     * Plain containment rather than a regex. In the stylesheet the class
     * `bg-[--x]` is escaped as `.bg-\[--x]`, so the four characters `-\[--` are
     * enough to find one and cannot be got wrong.
     */
    const css = builtCss();

    const marker = "-\\[--";
    const leaked = css
      .split(marker)
      .slice(1)
      .map((tail) => marker + tail.slice(0, 40));

    expect(
      leaked,
      `dead v3 utilities reached the built stylesheet: ${leaked.join(" | ")}`,
    ).toEqual([]);
  });
});
