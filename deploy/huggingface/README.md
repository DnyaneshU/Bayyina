---
title: Bayyina
emoji: 📋
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Check a Dubai rent increase against the published rules
---

# Bayyina · بيّنة

Check a Dubai rent increase against the published rules, and get the clause it
came from.

Enter what you pay now, what your landlord is asking for, and either the market
average or your area and property type. Bayyina applies **Decree 43 of 2013,
Article 1** — the banded rent-increase table — and tells you whether the increase
sits inside the published limit, with the text of the decree beside the encoding
we ran.

## What makes this different

**The rules engine is deterministic.** No language model computes any figure,
selects any band, or writes any part of the report. A model would be used at the
edges of a voice call to understand speech; it is structurally excluded from the
answer path, and a test walks the import graph to prove it.

**Every answer cites its clause.** Open *How we encoded the rules* to see the
published text beside our encoding of it — generated from the same band table the
evaluator reads, so a summary cannot drift from the logic that runs.

**Rules are signed.** Each rule file carries a SHA-256 signature over its own
bytes. Edit one without re-signing and the service refuses to start. The
signature on the provenance page is recomputed on every request, never echoed
from the file.

**"I don't know" is a real answer.** When there is too little registered-contract
data to stand behind a figure, Bayyina says so and quotes nothing, rather than
producing a confident number from thin evidence.

## What it is not

Not legal advice, and not an official determination. Bayyina is not a government
entity and does not act for any authority. Our encoding of these rules is pending
review by a qualified lawyer and says so on every result.

Market figures come from tenancy contracts published as open data by Dubai Land
Department. They are **not** the official RERA rental index and are never
described as one.

English only for now. Arabic and Malayalam are the product — a machine
translation of what a landlord may lawfully charge is worse than no translation,
because the reader cannot tell — so they wait for a native speaker.

## Source

[github.com/DnyaneshU/Bayyina](https://github.com/DnyaneshU/Bayyina) — including
the decision log, the guardrails, and how to reproduce the tamper demo in three
commands.

Built for the Ignyte × ElevenLabs Future of Voice AI Challenge.
