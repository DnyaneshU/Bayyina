# Bayyina — frontend

Vite + React 18 + TypeScript + Tailwind v4. Builds to static assets that the
backend serves in production, so the FE/BE split is a development concern and the
product still ships as **a single container**.

See [../README.md](../README.md) for the project, and
[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how it fits together.

## Running

```bash
npm install
npm run dev        # :5173, proxies /api and /healthz to the backend on :8000
```

The backend must be running for the health panel to resolve:

```bash
cd ../backend && uvicorn bayyina.api.app:app --reload
```

## Checks

```bash
npm run lint       # oxlint
npm run typecheck  # tsc -b, three projects
npm test           # vitest
npm run build
```

All four run in CI on every push.

## Two things that are not conventions here

**RTL is layout, not a font swap.** Arabic is a right-to-left *document*, so
`applyLanguage()` sets both `lang` and `dir` on the root element and every
component uses logical properties — `ms-*` / `me-*` / `ps-*` / `pe-*`, never
`ml-*` / `mr-*` / `pl-*` / `pr-*`. `src/test/rtl-safety.test.ts` scans the source
for physical utilities and fails the build on one. A layout that only mirrors its
text is a layout that looks wrong to half its users.

**An untranslated string must be visibly untranslated.** `ar.json` and `ml.json`
carry a `_TRANSLATION_STATUS` marker while their translations are pending, and
`src/i18n/locales.test.ts` enforces the invariant: a locale file either carries
the marker or is complete against `en.json`. Missing keys fall back to readable
English rather than to a raw key. Machine translation is not acceptable for any
user-visible string — see [../docs/GLOSSARY.md](../docs/GLOSSARY.md), where a
mistranslated disclosure is a compliance failure rather than a typo.

## Layout

```
src/
├── api/client.ts       typed backend client; network failure is a first-class path
├── i18n/               i18next setup, locale JSON, the locale-completeness test
├── test/               vitest setup and the RTL safety scan
├── App.tsx             scaffold shell — the real checker lands in T1.8
└── index.css           design tokens, per-language fonts, the RTL block
```
