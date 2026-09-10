# Malayalam evidence pack — not written

There is no `pack.txt.j2` in this directory, so `supported_languages()` does not
list `ml` and `build_pack(..., language="ml")` raises rather than quietly
producing an English document. That refusal is deliberate: the plan is explicit
that **an English PDF for a Malayalam or Arabic caller is a failed delivery**,
and a silent fallback is exactly how that happens unnoticed.

## What is needed

Copy `../en/pack.txt.j2` and translate the prose. Do **not** translate:

- the Jinja tags, filters or variable names
- `field_label` and `condition_wording` output — vocabulary lives in
  `bayyina/evidence/wording.py`, and Malayalam labels belong there, not in this
  template

## Rules that are not negotiable

1. Work from `docs/GLOSSARY.md`, not from the English template.
2. **Disclosures D1–D7 are not paraphrasable.** Translate the meaning exactly and
   have a second speaker check them.
3. **There is no official Malayalam legal register**, so unlike Arabic there is
   nothing to source. Prioritise clarity over formality, and raise anything that
   has no neutral Malayalam word rather than reaching for the nearest
   authoritative-sounding one.
4. The banned-word list in GLOSSARY section 1 applies in every language.
5. The document is read right-to-left. Keep the line width at 72 columns.

Adding `pack.txt.j2` here is the whole of the work — the language becomes
supported the moment the file exists, with no code change.
