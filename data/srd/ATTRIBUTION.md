# SRD data — source, version, and license

Per **OD-7** (ruled 2026-07-27) and **D-007**: the SRD dataset is *vendored* into this
repo and pinned to an exact upstream release. Version-pinning is a research
requirement — canon-drift measurement must not sit on shifting data.

## Required attribution

> This work includes material taken from the System Reference Document 5.1
> ("SRD 5.1") by Wizards of the Coast LLC and available at
> <https://dnd.wizards.com/resources/systems-reference-document>. The SRD 5.1 is
> licensed under the Creative Commons Attribution 4.0 International License
> available at <https://creativecommons.org/licenses/by/4.0/legalcode>.

## Edition

**D&D 5e SRD 5.1 — the 2014 rules.** Explicitly *not* the 2024 revision. The upstream
repo ships both; only `src/2014/en` is vendored here. Every rule the deterministic core
implements (D-001) is the 2014 ruleset, and the GM prompt should say so — a 2024-rules
answer is a canon defect, not a style difference.

## Pinned source

| | |
|---|---|
| Repo | <https://github.com/5e-bits/5e-database> |
| Release | `v5.10.0` |
| Commit | `3f5593ea004c4f5a2af95603087ce4de72689d9f` |
| Upstream path | `src/2014/en` |
| Fetched | 2026-07-27 |
| Vendored | 25 JSON files, ~4.0 MB, English only |

Exact per-file SHA-256 hashes are in `SOURCE.json`, generated from the bytes on disk
rather than hand-written. `dndc srd verify` re-hashes the vendored files and fails on
any mismatch, so silent drift in the pinned data is detectable.

The French, Portuguese, and Russian locales upstream are **not** vendored — the game
runs in English and they would triple the payload for nothing.

## Licensing — three layers, and they are not the same license

This is worth stating precisely, because the layers are easy to collapse into one.

1. **The game content** (spells, monsters, classes, conditions — the actual SRD 5.1
   text) is released by Wizards of the Coast under
   **[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode)** (January 2023).
   Full text: `LICENSE-CC-BY-4.0.txt`. This is the license D-007 and OD-7 refer to, and
   the one that obliges the attribution statement above.
2. **The database — its JSON structure, indices, and compilation** — is the work of the
   5e-bits contributors and is licensed **MIT**. Full text:
   `LICENSE-5e-database-MIT.md`.
3. **Upstream's own statement.** The 5e-database README describes the underlying
   material as released under the **Open Gaming License 1.0a**, not CC-BY-4.0 — it
   predates WotC's CC-BY release and was never updated. See the note below.

### Note on the OGL / CC-BY discrepancy

OD-7 records the dataset as CC-BY-4.0. Upstream's README says OGL 1.0a. Both describe
the same SRD 5.1 content, which WotC has made available under CC-BY-4.0 since January
2023 — the CC-BY grant is direct from the rights holder and does not depend on what a
downstream repo's README says. So the CC-BY-4.0 route in OD-7 holds; upstream's README
is simply stale.

This file therefore attributes under **CC-BY-4.0 for the content** and **MIT for the
database**, which satisfies both routes. Recorded here rather than resolved silently —
see the `FOR DESIGN:` note in `docs/PROGRESS.md`.

## Scope of what we use

`dndc srd ingest` normalizes the raw files into typed models under
`data/srd/normalized/`, which is **gitignored and never committed** (OD-7: a
normalization bug must not be freezable into the repo). Regenerate it, don't archive it.

Default ingest scope matches the P0.2 task note — classes L1–5, monsters CR 0–5 — and is
a parameter (`--max-class-level`, `--max-cr`), not a hardcoded limit, so widening it
later is a config change rather than a rewrite. The applied scope is recorded in the
normalized manifest.

## House rule

Original campaign content only. The SRD is reference data — **never** ingest a published
adventure module into this repo.
