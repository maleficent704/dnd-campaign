# PROGRESS.md — session continuity log

Newest entry first. See CLAUDE.md "Session protocol" for what belongs here.
**Read this file from the TOP** — the Open Decisions block below is the first thing a
session must check.

---

## Open decisions for Fable  ← kept at top for easy finding

Running list (maintained, not append-only). Items needing a Fable/Kelly ruling go
here; when resolved, move to "Ruled" with the resolution and record it in that day's
entry. Tag in-entry questions with `FOR DESIGN:` so they're greppable; promote real
blockers into this list.

### Open now

- **OD-11 — may the GM restate engine numbers in its prose?** Raised by P1.2 (2026-08-05),
  non-blocking. Given "2 slashing damage, HP now 11/20" as an engine result, the GM wrote
  "(2 slashing damage — you're at 11/20 HP.)". Legal under D-001 — it was given the
  numbers — but it duplicates what the CLI can render from state, and each restatement is
  a chance to transcribe a number wrong. Options and a lean are in the P1.2 entry below.
  Cheap to change before playtest transcripts exist; annoying after.

### Protocol in effect (Fable, 2026-07-27)

- **The docs are the channel.** No copy-paste through Kelly. Session start: read this
  file from the top, apply new rulings before code. Session end: dated handoff entry,
  `FOR DESIGN:` tags for anything needing a ruling. Work isn't done until the entry
  exists.
- **A Fable ruling takes effect only once recorded in the repo.**
- **One session, one commit. No code edits under a live play session.**

### Ruled 2026-08-04 (Fable, after P1.1 handoff)

- **OD-10 — cost model revised; toggle retained; default `api`.** The plan doc's
  "$1–5/session" is replaced by **~$0.50–2 measured** (Opus-heavy ceiling ~$5).
  OD-2's "max subscription value on light weeks" rationale is superseded by the
  measurement: ~30× scaffolding overhead means a subscription session spends ~4M
  pool tokens to save ~$1 metered — subscription mode is hereby the
  "pool-is-genuinely-idle / experimentation / Sam's-login" path, not the bargain
  path. Sticky default stays `api` for play sessions. Kelly may override from
  telemetry — per-session cost + would-have-cost logging keeps score. D-004 amended
  same day; planning-doc cost model updated.
- **The auth-trap fix is ratified into D-004** as a credential-isolation
  requirement (strip metered vars from child env; never copy the OAuth refresh
  token; pinned by test). This class of silent toggle inversion is exactly what
  the design must make impossible, not merely unlikely.
- **P1.1 deviations 1–4 approved.** `fallbacks` narrowed to the models that accept
  it (live-API catch — noted that smoke calls find what mocks cannot); `dndc gm`
  as the adapter proving ground; `anthropic` as a hard lazy-imported dependency
  (D-004 makes the api adapter v1-required); pricing block in config at standard
  (not introductory) rates — over-estimating beats under-reporting for
  measurement data.
- Known issues accepted (sub-cache-minimum smoke prompt, sticky-default side
  effect of testing, single-shot `on_text` in subscription mode, Ollama cost
  emission deferred to the tier that uses it).

### Ruled 2026-08-04 (Fable, after P0.5 handoff — Phase 0 complete)

- **OD-9 — D-008 vocabulary additions: both ratified, plus `call_id`.**
  `dirty_worktree` ratified (a SHA from a dirty tree is a false replay claim).
  `CallStatus` ratified as faithful implementation of the pending-state lesson.
  **`call_id` (uuid) added**: shared by the pending and terminal writes of a model
  call; `cost` events carry the same id. Rationale: adjacency pairing survives
  Phase 1 but breaks under Phase 4's interleaved two-endpoint NPC calls — decided
  now, before P1.1 writes to the schema. D-008 amended same day (vocabulary doc
  first, per its own rule).
- **P0.5 deviations 1–2 approved** (full vocabulary typed early = fix the contract
  now; `dndc campaigns` fine). Known issues accepted; the flush-without-fsync
  trade-off is explicitly endorsed for play sessions.

### Ruled 2026-07-27 (Fable, after P0.2 handoff)

- **OD-8 — license wording:** CC's analysis ratified. Rights-holder grant (WotC,
  SRD 5.1 under CC-BY-4.0 since Jan 2023) controls; upstream's OGL README is stale
  and cannot revoke it. The shipped three-layer ATTRIBUTION.md (CC-BY-4.0 content
  with WotC's paragraph verbatim + MIT database structure) stands as-is —
  conservative and correct. **OD-7 amended:** read its "CC-BY-4.0" as "content under
  CC-BY-4.0 per the rights holder; database structure under MIT; attribute under
  both" — no further doc changes needed.
- **Layout addition `src/dndc/srd/` approved** and ratified into the CLAUDE.md
  target layout (edited same day). Correct call: ingestion is none of
  rules/gm/memory/game; typed models correctly landed in `schema/`.
- **P0.2 deviations 1–3 approved.** Subclass-row filter (real corruption bug, test
  pinned); `IngestScope` as parameter with task defaults; `srd verify` beyond task
  scope — the pin is now enforced, which OD-7's research rationale requires.
- Known issues accepted (venv pytest note, console encoding, first-AC-entry with
  provenance kept, `srd` re-export shadow — all cosmetic or Phase-3-revisit).

### Ruled 2026-07-27 (Fable, after P0.1/P0.3/P0.4 handoff)

- **OD-7 — SRD source & vendoring:** Use `5e-bits/5e-database` (CC-BY-4.0, SRD 5.1
  content). **Vendor the raw dataset** into `data/srd/`, pinned to an exact
  release/commit recorded in `ATTRIBUTION.md` alongside the license text —
  version-pinning is a research requirement (canon-drift measurement must not sit on
  shifting data). The "never git a data dir" household rule targets private / large /
  regenerable data; a small, static, redistribution-licensed ruleset is a dependency
  lockfile, not a data dir. **Normalized output is regenerated by code, never
  committed** — a normalization bug must not be freezable into the repo. Note the
  edition explicitly (SRD 5.1 / 2014 rules) in ATTRIBUTION.md.
- **Deviations 1–3 all approved:** task reordering around the external P0.2
  dependency was correct; model ID bump is data maintenance (D-004/OD-3 ratify the
  tier, not the string); init commit is exempt from one-session-one-commit — the norm
  bars mid-session churn, not the mandated init. No squash.
- **Known issues accepted as cosmetic.** Logging-shadow confirmation owed at P0.5 as
  proposed; `.gitattributes` at CC's discretion.

### Ruled — awaiting implementation

- All of D-001…D-008 (initial architecture). Implementation = Phases 0–7 per TASKS.md.

---

## 2026-08-05 — P1.2 GM prompt assembly v1 (Claude Code, kelly-pc)

**Completed: P1.2.** 367 tests passing (48 new), suite still fully offline. The prompt was
also exercised against the live API — four calls, $0.045 total — which is where the two
findings below came from.

### What landed

- `gm/prompts/*.md` — six templates: `system_core` (with a `{{ scaffolding_directive }}`
  slot), one file per D-006 level, `context` (campaign state), `turn` (player input +
  engine results). Prose lives in files, per CLAUDE.md, so a prompt change reads as a
  prose diff.
- `gm/templates.py` — a deliberately dumb `{{ name }}` renderer. No conditionals, no
  loops: every decision about *what* goes in a section is made in Python where it is
  testable, and the template decides only *where* it lands. Substitution is strict **in
  both directions** — an unused value raises, because "the ledger stopped reaching the
  prompt after a rename" is the failure this module exists to prevent, and it is
  invisible in the output.
- `gm/canon.py` — the ledger **stub**: `CanonEntry` (id, text, scope, session/turn
  provenance, subject, tags), `CanonScope`, a container with YAML round-trip. No
  extraction, no supersession, no compression — Phase 2 owns those. The shape is the
  commitment; the machinery is not.
- `gm/context.py` — `CampaignContext` + `GMPromptBuilder`. D-002's prompt rule is
  implemented literally: the prompt is rebuilt every turn, and the recent window is
  bounded (`DEFAULT_WINDOW = 6` turns) rather than a growing transcript. A test pins that
  50 recorded turns still send 7 messages.
- `dndc gm` now uses the real assembly instead of P1.1's placeholder string, and gained
  `--campaign-name`, `--scene`, `--canon`, `--character` (repeatable), `--resolution`
  (repeatable), `--scaffolding`, and `--show-prompt`.

### The check-request convention (new, and P1.3 depends on it)

D-001 says the GM may *request* a resolution but never compute one. That rule is
unimplementable without telling the GM what to do **instead**, so `system_core.md`
specifies an exact form:

```
[[CHECK: <ability or skill> DC <number> — <what happens on a failure>]]
```

The GM sets the skill and the DC — that judgment is explicitly its job, and D-001 wants it
logged as a `gm_adjudication` — and then stops. **P1.3 parses this**; P1.2 only establishes
it. Verified live: handed "I try to force the rusted portcullis up with my bare hands," the
GM narrated the effort, stopped, and emitted
`[[CHECK: Strength DC 15 — the portcullis doesn't budge, and the water rises another few
inches while you strain]]`. Handed a failure plus damage as engine results, it narrated the
failure without softening it.

### Finding 1 — the cached prefix had to be split in two

`GMRequest` now carries `system` **and** `system_volatile`. Only `system` gets the cache
breakpoint. Without this, one hit point of damage invalidates the cached copy of the entire
instruction set, because caching is a prefix match — and `Usage`'s own docstring already
calls a permanently-zero `cache_read` a bug rather than a pricing detail.

Measured, and it works: system blocks are **1401 / 1247 / 1172 tokens** for high / low /
off scaffolding, so all three clear Sonnet 5's 1024-token cache minimum — which closes the
P1.1 known issue that flagged the smoke prompt as too small to cache. Consecutive live
calls reported `cache w1395` then `cache r1395`, i.e. a real cache hit with campaign state
changing underneath it.

### Finding 2 — "true" is not "known", and the first draft leaked

A live call with a `world`-scope entry reading *"a rusted winch mechanism is hidden under
silt in the north corner"* had the GM offer, as a menu option, "dig through the silt in the
north corner **where you noticed the winch mechanism**." Nobody had noticed anything. The
prompt said canon is true and never said it is not automatically *known*, so the GM treated
the whole ledger as the party's notes.

This is precisely the knowledge-leakage class this project exists to measure, and it showed
up on day one of having a prompt. `system_core.md` now states that being true is not being
known, that a concealed fact stays concealed until the players do something that would
plausibly find it, and that concealed things must never be surfaced as options. Re-tested:
the GM offered the same corner as an *observable cue* ("where debris keeps snagging") and
asked for a Perception check instead of handing the winch over. Pinned by a test.

Worth noting for Phase 4: the GM-only entry (the caravan master's sabotage) was **not**
leaked in either version — it foreshadowed without naming. Only the unmarked-but-hidden
case failed, which is the case with no label to hang the rule on.

### Deviations

1. **`GMRequest` gained a field** — a P1.1 API change made during P1.2. See Finding 1;
   doing it now avoided rewriting Phase 2's ledger consumer around a cache seam that was
   wrong. `full_system` collapses both halves for backends without block-structured
   caching (subscription, Ollama), so no adapter loses content. All four adapters have
   tests for the new shape.
2. **The `[[CHECK: ...]]` convention is specified here, not in P1.3.** It is prompt
   content, and the never-invent-mechanics rule is incomplete without it. Flagged because
   it is a wire format two tasks now share.
3. **`--character` / `--canon` / `--show-prompt` on `dndc gm`** beyond the task text.
   `--show-prompt` is the offline debugging tool for the builder and deliberately runs
   before any billing prompt or backend construction — inspecting a prompt must not need a
   key, a login, or a decision about who pays.
4. **Fixed a rich-markup bug in P1.1's code.** Streaming narration went through
   `console.print(chunk)` with markup enabled, so the GM's own `[[CHECK: ...]]` output
   would have been parsed as a style tag and swallowed. Now `markup=False`.

### Known issues / notes

- The chronicle layer (D-002's third tier) is not built; the recent window is the whole
  middle tier for now. Phase 2.
- `CampaignContext` is assembled from CLI flags, not loaded from `campaigns/<slug>/`.
  Wiring it to real campaign state belongs with P1.3's turn loop.
- Scaffolding costs real tokens: `high` is 229 tokens more than `off` on every turn.
  Cheap, but it is a per-turn cost, not a one-off.
- Ledger entries render in scope order, not insertion order, so prompt output is stable
  across runs — which is what makes the cached prefix cacheable at all.

### Recommended next task

**P1.3 — turn loop**: player input → intent pre-check → engine resolves → outcome handed to
the GM → narration → events logged. Everything it needs now exists: the builder takes
`resolutions` and returns a `GMRequest`, `Turn`/`CampaignContext.record()` maintain the
window, and the `[[CHECK: ...]]` form gives the pre-check something concrete to parse. The
first real piece of new work is parsing that form into a `gm_adjudication` event and
routing it to `rules/checks.py`.

**FOR DESIGN:** the GM restates engine numbers in its prose — asked to narrate "2 slashing
damage, HP now 11/20", it wrote "(2 slashing damage — you're at 11/20 HP.)". That is inside
the rules as written (it was *given* those numbers, not inventing them), and at a table it
reads naturally. But it duplicates something the CLI can render authoritatively from state,
and every restatement is a chance to transcribe a number wrong — a wrong number in prose is
exactly the desync D-001 is written to prevent, arriving by a side door. Options: (a) leave
it, (b) forbid restating numbers and let the CLI display mechanical results beside the
prose, (c) allow qualitative reference only ("the rust bites deep") with numbers reserved
to the UI. My lean is (c), but this is a table-feel question as much as a correctness one,
and it is cheap to change now and annoying to change after playtest transcripts exist.

---

## 2026-08-04 — P1.1 model adapters + OD-9 (Claude Code, kelly-pc)

**Completed: P1.1**, and **OD-9 implemented** as ruled. 319 tests passing (49 new), all
still offline. Both GM adapters verified end to end against live endpoints.

### OD-9 (ruled, now implemented)

`call_id` added to `gm_narration`, `npc_turn`, and `cost`. Tests pin that one model call
shares an id across its pending write, its terminal write, and its cost event — which is
the pairing that survives Phase 4's interleaved two-endpoint NPC calls.

### The auth trap — the most important thing in this entry

**Subscription mode was silently billing the API key.** Credential precedence is
`ANTHROPIC_API_KEY` → `ANTHROPIC_AUTH_TOKEN` → stored claude.ai OAuth login. Because
`.env` holds a key for the `api` adapter, a plain `claude -p` resolves to *that key* and
Claude Code prints only a mild warning. Measured on kelly-pc: a four-token reply cost
**$0.15 of metered API spend** while the CLI would have reported "subscription mode".
That is D-004's toggle inverted — the mode meant to protect the spend cap was the one
draining it.

`SubscriptionBackend.child_env()` therefore strips both metered variables from the child
environment so Claude Code falls through to the stored OAuth login it already refreshes.
We deliberately do **not** read `~/.claude/.credentials.json`: copying a refresh token
into our process would duplicate a secret and fight the refresh cycle. An explicit
`auth_token` is supported for pinning one. There is a direct test for this.

### Cost finding — subscription is not the cheap path

Same prompt, same model, both adapters, measured:

| path | tokens | cost |
|---|---|---|
| `api` | 104 in / 99 out | **$0.0018** |
| `subscription` | 2 in / 94 out **+ ~34k scaffolding** | **$0.0599** would-have-cost |

Headless Claude Code carries its own system prompt and tool definitions — ~33–40k tokens
**per invocation**, cache-read after the first. `--system-prompt` replaces the persona
but not the tooling, so the floor stays. In dollars subscription mode is free (it draws
the weekly pool), but a 3-hour session at 80–120 turns is ~4M tokens of pool on
scaffolding alone. See `FOR DESIGN:` below — this bears on the plan doc's cost model.

### Adapters

- `models/base.py` — `GMBackend`, `GMRequest`, `GMResponse`, `Usage`. No vendor SDK is
  imported here, and adapters import theirs lazily, so the rules core and the whole test
  suite work with nothing installed.
- `models/api.py` — Anthropic SDK, always streaming (a narration turn is long, and
  streaming is what keeps a large `max_tokens` off the HTTP timeout). Three request-shape
  rules encoded because each is a documented 400 on Sonnet 5 / Opus 5: **no sampling
  parameters**, **no `budget_tokens`**, and **refusals are not exceptions** — a declined
  request is HTTP 200 with `stop_reason == "refusal"` and empty content, so `refused` is
  checked before the text is trusted. System prefix carries the cache breakpoint.
- `models/subscription.py` — `claude -p --output-format json`, parsed against the real
  schema (captured live, not guessed): `result`, `usage.*`, `total_cost_usd`,
  `duration_ms`, `is_error`. Tolerates Claude Code printing a warning before the JSON.
- `models/ollama.py` — native `/api/chat` over stdlib HTTP; no dependency for one JSON
  POST. Reports `reported_usd=0.0` — local inference is free, which is a fact, not an
  unknown.
- `models/mock.py` — records every request, so Phase 1 can assert on what the prompt
  builder actually sent. This is what keeps the suite offline.
- `models/pricing.py` — prices from `config.yaml`. An unpriced model returns `None`
  rather than a guess: Phase 7 reads the cost log as measurement, and a wrong number
  there is worse than a missing one.

### CLI

`--billing api|subscription`, a session-start prompt defaulting to the sticky value, and
the subscription throttle warning. The choice writes back as the new default via a
targeted line edit — a pyyaml round-trip would strip every comment, and the comments in
`config.yaml` are the only place several decisions are explained. New `dndc gm "..."`
runs one narration turn end to end and emits `gm_narration` + `cost` sharing a `call_id`.

### Deviations

1. **`fallbacks` is narrower than the docs implied.** The skill guidance recommends
   opting into server-side refusal fallbacks for Opus-5-class models. I initially gated
   on "models that can refuse", which included Sonnet 5 — the live API rejects that with
   `400: 'claude-sonnet-5' does not support the 'fallbacks' parameter`. Now gated on
   opus-5/fable-5/mythos-5 only; refusal *handling* stays unconditional. Caught by the
   end-to-end call, not by the unit tests — worth remembering.
2. **Added `dndc gm`** beyond the task list. P1.1 requires a billing prompt and a
   `--billing` flag, which need somewhere to live, and a one-shot turn is what proves the
   seat works before the P1.3 turn loop exists.
3. **`anthropic` added to dependencies** rather than an extra. D-004 makes the `api`
   adapter a v1 requirement, so it is not optional — but it is imported lazily so its
   absence degrades to a clear error instead of breaking the rules core.
4. **Pricing block added to `config.yaml`.** P0.5 flagged that would-have-cost needs a
   price table and that config was the right home; this implements that. Standard rates,
   not Sonnet 5's introductory $2/$10 (live through 2026-08-31) — deliberately
   over-estimating rather than under-reporting.

### Known issues / notes

- `dndc gm`'s smoke system prompt is ~50 tokens, under Sonnet 5's 1024-token cache
  minimum, so it reports `cache w0`. Correct, not a caching bug — the real Phase 2
  ledger-backed prompt will clear the threshold easily.
- My smoke test flipped the sticky default to `subscription`; restored to `api`. Worth
  knowing the feature has that side effect when testing.
- The subscription adapter returns the whole turn at once (headless mode has no token
  stream), so `on_text` fires once. Callers use one code path either way.
- `estimate_cost` covers the GM seat only; nothing emits `cost` for the Ollama seats yet.

### Recommended next task

**P1.2 — GM prompt assembly v1**: system template (tone, D-006 scaffolding parameter, the
never-invent-mechanics rule), context builder over a canon-ledger stub, templates under
`src/dndc/gm/prompts/`. The mock backend makes this fully testable offline, and it is
what turns `dndc gm`'s placeholder system prompt into the real thing.

**FOR DESIGN:** the plan doc estimates "$1–5/session at Sonnet API rates" and treats
subscription mode as the way to stretch value on light coding weeks. The measurement
above complicates that: headless Claude Code adds ~34k tokens of scaffolding *per turn*,
so a 3-hour session is roughly 4M pool tokens before any campaign content. The API path
looks far cheaper than the estimate ($0.0018 for a small turn), and the subscription path
far heavier than "free" implies. Nothing is blocked — the toggle works and both paths are
measured — but OD-2's rationale ("max subscription value on light coding weeks") may want
revisiting now there are numbers, and the plan doc's cost model probably wants updating.

**Completed: P0.5.** 267 tests passing (77 new), still zero network, GPU, or API key.
**Phase 0 is done** — P0.1–P0.5 all landed. Next phase is P1.1 (model adapters), which
is the first task that needs Kelly's API key in `.env`.

### D-008 event vocabulary, typed

`schema/events.py` implements all nine families — `session_meta`, `player_input`,
`rules_resolution`, `gm_adjudication`, `gm_narration`, `npc_turn`, `canon_write`,
`escalation`, `cost` — as frozen pydantic models behind a discriminated union on `type`.
A test asserts the family set is exactly D-008's nine, so drift between the doc and the
code is a test failure rather than a discovery in Phase 7.

Typing the whole vocabulary now (rather than only `session_meta`, which is all P0.5
strictly required) means Phases 1–4 emit into a fixed contract instead of inventing
fields as they go. Two fields carry the load for the research side:

- `rules_resolution` records the seed, the expression, and **every individual die face**,
  not just the total — a logged session replays exactly.
- `gm_adjudication.resolution_seq` points at the `rules_resolution` it governed, so
  "was the GM fair?" is a query over pairs rather than a reading exercise.

### Logger

- `logging/emitter.py` — `SessionLog`, append-only, one JSON object per line, opened in
  append mode and flushed per write. Nothing rewrites or truncates a written line.
- `seq` is assigned by the emitter, never by callers, so two components cannot race to
  the same number. **Reopening a log resumes `seq` from the highest value on disk** —
  the npc-village continuity rider, which otherwise bites the first time a process
  restarts mid-session. Tested.
- Reading is deliberately tolerant: a truncated final line from a hard crash is skipped
  rather than poisoning the rest of the session.
- `session_meta` stamps the commit SHA **and** a `dirty_worktree` flag, plus the resolved
  seats read from `config.yaml` (never a hardcoded model id), gameplay settings, and the
  master seed.

### CLI

`new-campaign`, `roll`, `sheet show`, `sheet validate` — plus `campaigns` (listing).
`roll` always resolves and prints a seed even when none was given, because an unrecorded
roll is not reproducible and reproducibility is the entire point of the deterministic
core. `--log` writes a real `session_meta` + `rules_resolution` pair, which is what
proves the logger end to end. `sheet show` renders abilities/saves/skills/inventory/slots
via rich; `sheet validate` reports the offending field rather than a stack trace.

`schema/campaign.py` + `game/campaign.py` lay out `campaigns/<slug>/` with
`characters/` and `saves/`. Creation **refuses to touch an existing directory** — from
Phase 2 that would destroy the canon ledger, which is not something to do as a side
effect of a mistyped name. `slugify` escapes the Windows reserved device names
(`nul`, `con`, `aux`, `prn`, `com1-9`, `lpt1-9`) rather than rejecting them.

### Logging-shadow question — resolved (owed to Fable's 2026-07-27 ruling)

**`src/dndc/logging/` is safe; keeping it.** Python 3 has no implicit relative imports,
so an absolute `import logging` anywhere — including inside the package itself —
resolves to the standard library. The shadow exists *only* for the expression
`from dndc import logging`, which nothing does. Confirmed two ways: an in-process
assertion that `sys.modules["logging"]` is untouched, and a subprocess that imports
`dndc.logging` **first** and then asserts a bare `import logging` still lands on the
stdlib file. The CLAUDE.md layout stands unchanged.

### Deviations

1. **Typed all nine D-008 families, not just `session_meta`.** See above — the contract
   is cheaper to fix now than after four phases have written to it.
2. **Added `dndc campaigns`** beyond the four named commands. Five lines, tested, and it
   answers "where did my campaign go" without a filesystem hunt.
3. **Two fields beyond D-008's literal text** — flagged below for ratification.

### Known issues / notes

- `roll --log` opens a *new* session log per invocation; there is no persistent session
  object until the Phase 1 turn loop. Fine for a one-shot roll, not a session.
- The `cost` event is typed but nothing emits one yet. Populating `usd` in subscription
  mode needs an API price table, which does not exist in `config.yaml` — that belongs to
  P1.1 ("would-have-cost calc") and should probably live in config rather than code, so
  a price change is data maintenance.
- `_write` flushes but does not `fsync`. Durable against a process crash, not against a
  power cut. Correct trade for a play session; revisit only if it ever bites.
- Test suite is 0.95s and still needs no network, GPU, or key.
- Run tests as `./.venv/Scripts/python.exe -m pytest` — the global Python has a broken
  `logfire` pytest plugin that crashes collection before any test runs.

### Recommended next task

**P1.1 — model adapters** (`GMBackend` interface, `api` + `subscription` adapters, Ollama
adapter, mock backend, session-start billing prompt). This is the first task that needs
**Kelly's API key in `.env`**; the `subscription` adapter can be built and tested against
her existing CC login without it, and the mock backend keeps the test suite offline.

**FOR DESIGN:** two additions to the D-008 vocabulary, made because D-008 says to extend
the doc *first*, so these want ratification (or removal) before Phase 1 writes to them:

1. **`CallStatus` (`pending` / `complete` / `failed`) on `gm_narration` and `npc_turn`.**
   D-008's rationale explicitly carries the mystery's pending-state lesson — "log intent
   before external calls so crashes are reconstructable" — so this implements stated
   intent, but the enum itself is a new field. Note it makes a model call *two* writes;
   I did not invent a correlation id to pair them, leaving that to P1.1 when real calls
   exist. If Fable wants exact pairing, that is a third field and worth deciding now.
2. **`session_meta.dirty_worktree`.** D-008 says "includes commit SHA"; this adds whether
   the tree was dirty. A SHA from a dirty tree does not describe the code that ran, so a
   replay claim based on it alone would be false — but it is strictly an addition.

---

## 2026-07-27 — P0.2 SRD ingestion (Claude Code, kelly-pc)

**Completed: P0.2**, implementing OD-7 as ruled. 190 tests passing (59 new), still zero
network, GPU, or API key. Phase 0 now has only **P0.5** outstanding.

### Vendored dataset

- `5e-bits/5e-database` pinned to release **v5.10.0**, commit
  `3f5593ea004c4f5a2af95603087ce4de72689d9f`, upstream path `src/2014/en` — SRD 5.1,
  the **2014** rules. 25 JSON files, ~4.0 MB, committed under `data/srd/raw/`.
- Only the English locale is vendored; fr/pt/ru would triple the payload for nothing.
- `data/srd/SOURCE.json` carries per-file SHA-256 hashes and is **generated from the
  bytes on disk**, not hand-written, so it cannot drift from what it describes.
  `dndc srd verify` re-hashes and fails on mismatch — the pin is enforced, not asserted.
- `data/srd/ATTRIBUTION.md` carries WotC's required attribution paragraph verbatim, the
  edition note, the pin, and the three-layer license breakdown. Full CC-BY-4.0 and MIT
  texts sit beside it.
- `data/srd/normalized/` is gitignored (OD-7: a normalization bug must not be freezable
  into the repo). Verified with `git check-ignore`.

### Code

- `schema/srd.py` — typed models for species/subspecies, classes with per-level
  progression, spells, monsters, equipment, conditions, plus `SRDData` as the whole
  ruleset. All frozen: nothing in the engine may mutate the rules.
  **Monsters reuse `AbilityScores` from the character sheet**, so a stat block and a PC
  resolve modifiers through identical code — the rules engine does not care which side
  of the screen a creature is on.
- `srd/ingest.py` — normalizes the upstream API dump into those models. Upstream nests
  every cross-reference as `{index, name, url}` and stores movement as prose ("30 ft.");
  ingestion flattens both, so nothing downstream depends on the shape of somebody
  else's REST API and no prose is re-parsed at runtime. Output is sorted, so a re-run
  over unchanged input is byte-identical (tested).
- `srd/validate.py` — referential integrity across collections, plus a dice check
  (below).
- `srd/repository.py` — `SRDRepository`, case-insensitive lookup by index *or* name.
  The GM says "Fire Bolt", the data says "fire-bolt"; resolving that is a data concern,
  not something to leave to a model.
- `game/cli.py` — added the `srd` group: `ingest` (with `--max-class-level` / `--max-cr`),
  `stats` (the task's sanity command), `verify`. `--version` / `--check-config` unchanged.

### Two findings worth recording

1. **`"1d8 + MOD"` is not a dice expression.** Six spells (Cure Wounds, Healing Word,
   Mass Cure Wounds, Mass Healing Word, Prayer of Healing, Spiritual Weapon) store
   amounts with a symbolic `MOD` placeholder for the caster's spellcasting modifier.
   Handed to `dice.roll()` unchanged, that is a `DiceError` thrown mid-session. Ingestion
   now strips it to a rollable `"1d8"` and raises `Spell.adds_spellcasting_modifier`
   instead; the caller adds the modifier from the sheet. Mixed usage within one spell is
   a hard error rather than a guess.
2. **All 150 distinct dice strings in the dataset are now validated at ingest time**
   against the P0.3 parser. This is the general fix for finding 1 — if upstream adds
   another placeholder, `dndc srd verify` reports it instead of the table discovering it.
   A nice side effect: it is a real cross-check between P0.2 data and the P0.3 engine.

### Correctness spot-checks (counts alone prove nothing)

Wizard L5 slots 4/3/2 and PB 3; Goblin AC 15 / HP 7 / CR ¼ / +4 scimitar 1d6+2 / Dex +2;
plate AC 18, Str 15, stealth disadvantage; longsword 1d8 versatile 1d10. All match SRD
5.1. Counts: 9 species, 4 subspecies, 12 classes (8 casters), 319 spells (24 cantrips),
245 monsters CR 0–5, 237 equipment, 15 conditions.

### Deviations

1. **Subclass level rows must be excluded from class progression.** `5e-SRD-Levels.json`
   holds 290 entries, but 50 are *subclass* levels carrying a `subclass` key and no
   `prof_bonus`. Merging them would have corrupted the level table (and crashed on the
   missing field). Filtered explicitly, with a test pinning it.
2. **Ingest scope is a parameter, not a constant.** The task note says classes L1–5 and
   monsters CR 0–5; those are the *defaults* of `IngestScope`, overridable from the CLI.
   Phase 3 will want a higher CR ceiling and should not need a rewrite to get one.
3. **Added `dndc srd verify`** beyond the task's `stats`. A pin whose drift is undetectable
   is a comment, not a lock, and OD-7 leans on the pin for research validity.
4. **New `src/dndc/srd/` subpackage**, which is not in the CLAUDE.md target layout.
   Ingestion is not rules, GM, memory, or game. The typed models did go to `schema/`, which
   the layout already earmarks for "monsters, spells". Flagging as a layout addition, not
   a contradiction — no ratified decision speaks to it.

### Known issues / notes

- The repo has a `.venv/`; the global Python has a broken `logfire` pytest plugin that
  crashes collection. Run tests as `./.venv/Scripts/python.exe -m pytest`.
- `dndc srd stats` renders an em dash as `?` when piped through Git Bash on Windows.
  Console encoding only — fine in a real terminal.
- `Monster.armor_class` takes the first of upstream's AC entries; a handful of monsters
  list conditional alternatives (mage armor, barkskin). The provenance is kept in
  `armor_class_kind`. Adequate for Phase 3; revisit if a conditional AC actually matters
  at the table.
- `dndc.srd.__init__` re-exports the `ingest` function, which shadows the `ingest`
  submodule for `from dndc.srd import ingest`. Intended usage is the function; import
  the module path explicitly if you need the module. Same family as the `dndc.logging`
  shadow already noted — still cosmetic.

### Recommended next task

**P0.5** (CLI skeleton + JSONL logger), which closes Phase 0. The `srd` group already
established the subparser structure, so `new-campaign` / `roll` / `sheet show|validate`
slot in beside it. P0.5 also owes the confirmation on the `dndc/logging` stdlib-shadow
question, per Fable's 2026-07-27 ruling.

**FOR DESIGN:** the OGL-vs-CC-BY discrepancy is written up as **OD-8** in the Open block
at the top of this file. Non-blocking — P0.2 is complete and attributes under both
licenses — but OD-7's wording says CC-BY-4.0 where upstream says OGL 1.0a, and it is
worth one sentence from Fable on whether to amend OD-7 rather than leaving the two docs
disagreeing.

---

## 2026-07-27 — P0.1, P0.3, P0.4 (Claude Code, kelly-pc)

**Completed: P0.1, P0.3, P0.4.** 131 tests passing, zero network or GPU needed.

### P0.1 — repo init
- `pyproject.toml` (hatchling, src layout, py3.11+): pydantic, pyyaml, rich; pytest
  as a dev extra; `dndc` console entry point.
- Package skeleton per CLAUDE.md layout, each subpackage carrying a docstring that
  states its contract.
- `src/dndc/config.py` — typed pydantic loader for config.yaml with
  `extra="forbid"`, so a config typo fails loudly instead of silently defaulting.
  This is the single route to any model name or endpoint.
- `game/cli.py` — entry-point stub with `--version` and `--check-config`. Real
  command surface still owed by P0.5.
- `.gitignore`: added build artifacts and `campaigns/*/saves/`.
- Ran `scripts/install-hooks.sh`. Renamed `master` → `main` before the first commit
  (zero commits existed, so this was free).

### P0.3 — dice + rules primitives
- `rules/dice.py`: expression parser (`2d6+3`, `4d6kh3`, `2d20kl1`, negative terms,
  `kh`/`kl`/`dh`/`dl`), `roll()` and `roll_d20()` over an explicit
  `random.Random` — no implicit global RNG anywhere, so every roll is reproducible
  from a recorded seed. `net_advantage()` implements the 5e cancel rule.
- `rules/checks.py`: `ability_modifier`, `proficiency_bonus`,
  `proficiency_contribution` (none/half/proficient/expertise), `resolve_check`,
  `resolve_save`, `resolve_attack`. Attack rules encoded: nat 20 always hits and
  crits, nat 1 always misses, crit doubles dice but not the flat modifier, damage
  floors at 0. Checks deliberately do *not* auto-succeed on a nat 20 — that rule is
  attacks-only in 5e, and there is a test pinning it.
- `CheckResult` carries the DC it was resolved against, so a `gm_adjudication`
  event can be audited against its `rules_resolution` event later (D-008).

### P0.4 — sheet schema + allocators
- `schema/sheet.py`: full L1 sheet — abilities (with the 5e 1..30 bound), the 18
  SRD skills with their governing abilities, proficiencies (saves/skills/armor/
  weapons/tools/languages), HP with temp, AC, speed, inventory, spell slots.
  Derived values (proficiency bonus, save/skill modifiers, passive Perception,
  initiative, carried weight) are computed properties, never stored — nothing can
  drift out of sync with the scores.
- Cross-field validators: current HP ≤ max, expended slots ≤ total, spell slot
  levels 1..9, no duplicate save proficiencies. Temp HP is deliberately *not*
  bounded by max (it sits on top of the pool).
- YAML round-trip via `to_yaml`/`from_yaml`/`save`/`load`, verified both in-memory
  and through a file. Emitted YAML is plain and hand-editable (D-005: sheets are
  re-editable data).
- `rules/allocate.py`: `assign_standard_array` (must be a permutation of
  15/14/13/12/10/8), `assign_point_buy` (SRD cost table, 27-point budget,
  underspend allowed / overspend rejected), `point_buy_breakdown` for showing a
  player their spend, and `apply_bonuses` for species/feat increases applied
  *after* allocation — which is why 15 + 2 = 17 is legal under point buy.

### Deviations
1. **Worked P0.3 and P0.4 before P0.2.** P0.2 needs an external SRD dataset fetch
   plus a source/version/licence decision; P0.3 and P0.4 are pure and block
   nothing. Nothing in P0.3/P0.4 depends on P0.2. P0.2 is still owed.
2. **Bumped the GM seat model IDs** in `config.yaml`: `claude-sonnet-4-6` →
   `claude-sonnet-5`, `claude-opus-4-8` → `claude-opus-5`. D-004 and OD-3 ratify
   the *tier* (Sonnet-class default, Opus escalation at authored threshold
   moments), not a version string, so this is data maintenance, not a decision
   change. The old IDs are still served, so nothing was broken — just stale.
3. **Two commits this session, not one.** P0.1's task text explicitly calls for a
   first commit at repo init; the rest of the session is the second. Reading
   "one session, one commit" as a norm against noisy history rather than a bar on
   the mandated init commit. If Fable disagrees, squash on the next pass.

### Known issues / notes
- `src/dndc/logging/` shadows the stdlib `logging` name for `from dndc import
  logging`. Absolute imports inside it resolve to the stdlib normally, so this is
  cosmetic, but P0.5 should confirm it when the JSONL emitter lands. Layout comes
  from CLAUDE.md, so it was not changed unilaterally.
- Emitted `spell_slots` keys serialise as quoted strings (`'1':`). Both the quoted
  and the hand-written unquoted form load correctly — verified — but it looks odd
  in a hand-edited file. Cosmetic only.
- `git` reports CRLF conversion warnings on every file (Windows default). Harmless;
  a `.gitattributes` would silence it if it becomes annoying.
- No git remote is configured yet. Kelly's prep item — a private GitHub remote —
  is still open, so nothing has been pushed. The Secrets & Data staged-diff sweep
  was run before both commits and came back clean (no `.env`, no venv, no logs
  tracked; the only key-shaped string in the repo is the `sk-ant-...` placeholder
  in `.env.example`).

### Recommended next task
**P0.2 (SRD ingestion).** It is the only remaining Phase 0 item that P0.5 partly
leans on (the `sheet validate` command is more useful against real class/species
data), and it is the one task in Phase 0 with an external dependency, so it is
worth doing while there is room to make the licence and source decision carefully.
Then P0.5 to close out Phase 0.

**FOR DESIGN:** P0.2 asks for "a CC-BY 5e SRD structured dataset" without naming
one. The obvious candidate is `5e-bits/5e-database` (CC-BY-4.0, the dataset behind
dnd5eapi.co) — well-structured JSON, actively maintained, already scoped roughly to
SRD content. Alternative is parsing the official SRD PDF ourselves, which is more
work and more error-prone but gives exact control over what lands in `data/srd/`.
Ruling wanted on: (a) which source, and (b) whether the dataset is vendored into
the repo or fetched by a script at setup time. Vendoring makes the repo
self-contained and pins the version — which the research instrumentation wants,
since canon-drift measurements should not shift under us — but adds a few MB of
JSON to a code repo, which cuts against the "never git a data dir" rule in the
household Secrets & Data policy. My read is that vendoring is correct here
(the SRD is small, static, licensed for redistribution, and version-pinning is a
research requirement), but this is exactly the kind of call that should be ratified
rather than assumed.

---

## 2026-07-27 — scaffold created (Fable, Claude.ai project space)

- Repo scaffold authored: CLAUDE.md, DESIGN-DECISIONS.md (D-001…D-008), TASKS.md
  (P0.1–P1.5 detailed, Phases 2–7 outlined), this file, config.yaml skeleton,
  .env.example, .gitignore, `/pickup` + `/handoff` commands, install-hooks.sh.
- Phase plan + OD register also live in
  `race-control/docs/planning/active/2026-07-27-dnd-campaign-companion.md`.
- Kelly's prep items (not blockers for P0.1–P0.5): API key in `.env` with console
  spend cap (needed at P1.1 for the `api` adapter); private GitHub remote; Ollama on
  sam-pc before Phase 4.
- **Recommended next task: P0.1.** Run `scripts/install-hooks.sh` after `git init`.
