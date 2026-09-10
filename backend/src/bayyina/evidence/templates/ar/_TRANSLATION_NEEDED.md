# Arabic evidence pack — not written

There is no `pack.txt.j2` in this directory, so `supported_languages()` does not
list `ar` and `build_pack(..., language="ar")` raises rather than quietly
producing an English document. That refusal is deliberate: the plan is explicit
that **an English PDF for a Malayalam or Arabic caller is a failed delivery**,
and a silent fallback is exactly how that happens unnoticed.

## What is needed

Copy `../en/pack.txt.j2` and translate the prose. Do **not** translate:

- the Jinja tags, filters or variable names
- `field_label` and `condition_wording` output — vocabulary lives in
  `bayyina/evidence/wording.py`, and Arabic labels belong there, not in this
  template

## Rules that are not negotiable

1. Work from `docs/GLOSSARY.md`, not from the English template.
2. **Disclosures D1–D7 are not paraphrasable.** Translate the meaning exactly and
   have a second speaker check them.
3. **Legal citations keep their official Arabic form.** Decree 43/2013 and Law
   26/2007 were written in Arabic; our English is an unofficial translation of
   them. Back-translating our English would be producing a third-hand version of
   a text that already exists — source the official wording instead. This is the
   blocker, and it is why nobody has simply drafted this file.
4. The banned-word list in GLOSSARY section 1 applies in every language.
5. The document is read right-to-left. Keep the line width at 72 columns.

Adding `pack.txt.j2` here is the whole of the work — the language becomes
supported the moment the file exists, with no code change.
