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

**Nothing ruled is unbuilt. Phase 4 is complete** — P4.1–P4.7 landed 2026-09-02 (b)–(g)
and 2026-09-03. The GM directs, NPCs answer for themselves on toto-llm, their drafts are
gated, changes of mind supersede the beliefs they replace, and the tier has been verified
end to end against a real campaign (`docs/playtests/2026-09-02-npc-tier-verification.md`).

**Phase 5 is complete** — P5.1–P5.4 landed 2026-09-03 (b)–(e). A session that is
interrupted survives being interrupted and picks up in the same log where it stopped; the
analysis side reads the restart honestly; a campaign picked up again reads itself back to
the table, including where the party is standing; and an evening now says what it cost, in
both of the currencies it spends — **$0.2428 of API billing across the whole campaign to
date, and one 65-second wait for a cold 70B.**

**Phases 0–5 are built. Phase 6 (the LAN GUI) is under way** — planned as six tasks and
P6.1 landed 2026-09-03 (g). **Nothing ruled is unbuilt.**

P5.5 (2026-09-03 (f)) closed the one defect Phase 5 found in itself: nothing recorded a
player character's pronouns, so every layer re-derived them from prose and the chronicler
— which reads a transcript with no roster — got Corin Vale wrong 3 times in 4. It is
recorded on the sheet now. **Kelly and Sam: the two Salt Road sheets were backfilled from
the logs rather than asked about, and either is one line to change.**

Three questions are open, none blocking:

> **1. Should a GM declare a change of mind before the character has conceded it out
> loud?** (New, 2026-09-03.) P4.6 works and the GM never used it: across nine turns built
> to force it — the frayed tie, the dry boots, the recovered crate, Hammond asking him
> point-blank — it narrated the guard's certainty cracking beautifully and tagged nothing,
> and the guard said *"Yes, I still think Vale here took my crate."* I think it was right
> every time: a man wavering has not changed his mind. But the loop is self-stabilising in
> a way worth ruling on — the belief says he "is not interested in other explanations", so
> the 70B plays him stubborn, his stubborn line rides into the GM's window, and the GM
> declines to declare a change it can see has not happened. A character can be
> *structurally* unable to be talked round. Roughly: leave it and let changes be rare · tell
> the GM that narrating somebody as convinced **is** the moment to tag · or move the trigger
> to the character, so the tag follows an NPC line that concedes. Nothing is blocked either
> way; the machinery is built, tested and controlled.

> **2. Should the GM voice player characters at all, now that NPCs voice themselves?**
> (New, 2026-09-02 (g).) In a ten-turn scene the GM rendered the declared action as quoted
> PC speech every single turn — *"The canvas flap was already loose when I got to it," she
> says*. This is not new and P4.5 did not cause it; it is how social actions have been
> narrated since Phase 1, and the prose is good. But the NPC tier has made it
> **asymmetric**: the cast now speak in their own voices, and the player characters are the
> only people at the table being ventriloquised. Roughly: leave it · let the GM describe a
> PC speaking but not quote them · or hold that a PC's words belong to their player. This
> is a feel question about a table Fable has never sat at, so **Kelly's view probably counts
> for more than a ruling** — and nothing is blocked either way.
>
> **3. Should a `blocked` line cost the turn, or fall through to the GM narrating around
> the silence?** (Carried from (d).) P4.5 takes the neutral position — nothing is shown and
> nothing enters the GM's window — so either answer stays cheap. New datum from (g): across
> seven live lines and twenty-four control cases **nothing was ever blocked.** The gate
> revises; it does not silence. This may be a rarer case than it looked.

One item is **provisionally accepted rather than settled** — Kelly's, not Fable's:

> **The generated-background register: unsure, held open (Kelly, 2026-09-02).** She read
> *Coast-Road Grifter* (quoted in the entry below), said it looks right, and explicitly
> declined to call it: **not enough evidence yet to tell whether it is a problem.** So the
> veto is neither exercised nor spent. Not blocking anything, and no ruling is wanted.
>
> **Trigger to revisit:** the table finding an invented background flat, generic, or wrong
> in tone *during play* — a second or third one that reads like the first, a background
> nobody refers to again. That is a prompt change (`creation_core.md`, the *Backgrounds are
> yours to write* section), not a design one, and reversible in an evening. Do not tune it
> speculatively; one sample is one sample.

*(Both halves of the 2026-08-15 (c) ruling are now built: monster tactics 2026-08-15 (j),
backgrounds 2026-09-02.)*

*(Drift-baseline reproducibility ruled 2026-08-15 — implemented 2026-08-15 (c).)*

*(The 2026-08-14 block below is ruled; both CC-owned items — the utility seat split and
the sweep's display grouping — were implemented 2026-08-15.)*

*(OD-15 was ruled 2026-08-05 and implemented 2026-08-09 — see below.)*

### Protocol in effect (Fable, 2026-07-27)

- **The docs are the channel.** No copy-paste through Kelly. Session start: read this
  file from the top, apply new rulings before code. Session end: dated handoff entry,
  `FOR DESIGN:` tags for anything needing a ruling. Work isn't done until the entry
  exists.
- **A Fable ruling takes effect only once recorded in the repo.**
- **One session, one commit. No code edits under a live play session.**

### Ruled 2026-08-15 (c) (Fable, mid-Phase-3, on the two open questions)

**Date correction (Fable, 2026-08-15):** the two questions above arrived carrying
future dates (08-16, 08-17, 08-21) — today is 2026-08-15, and the pattern (one day
incremented per session) suggests dates were inferred rather than read from the
clock. This block was briefly headed 08-21 by the same propagation; corrected. CC:
at next session, (1) verify against `git log` commit timestamps and correct the
affected entry dates in this file (suffix same-day sessions (b), (c)… as the 08-15
P2.6 entry already did), and (2) note the root-cause fix now in CLAUDE.md — entry
dates come from the system clock, never from inference. Confabulated provenance in
the drift instrument's own log is a finding worth the two-line fix.

- **Monster tactics: the GM chooses, via tag, in the narration call it already
  makes — deterministic policy becomes the logged fallback.** Target selection is
  *categorical* judgment ("who does the goblin attack" needs no numbers), squarely
  the GM's side of D-001 under OD-12's own test. Replayability was solved by the
  DC precedent: replay reads logged judgments instead of re-asking — a logged
  target choice is no different from a logged DC. Shape: a declaration tag in the
  existing per-monster-turn narration call (sixth use of the convention; the `[[`
  filter already hides it; zero extra calls), engine resolves the declared action
  deterministically, and a missing/unparseable declaration falls back to the
  most-wounded policy **with the fallback logged**, so fights never stall and
  Phase 7 sees exactly what happened. Feel: deterministic-only targeting is
  exploitable and flattens monster personality — cowards, packs, and captains
  fighting differently is GM craft this project exists to host. Wire format and
  event fields are CC's, doc-first per D-008; logged tactical choices are a new
  Phase 7 fairness/aggression instrument for free.
- **Backgrounds: option 3 — co-creation proposes an original background, engine
  validates the shape, table confirms, filed as campaign data.** Most D-007-native
  answer: the background *mechanism* (name, two skills, small extra, flavour) is
  uncopyrightable mechanics; the generated names/text are original and
  campaign-native — Corin gets her own grifter history, not the PHB's list.
  Constraints: shape enforced deterministically (exactly two skills from the
  standard list, ≤1 tool or language, **never** numeric bonuses), proposals must
  not duplicate class skill picks (the P1.4 double-granting trap), confirmed
  backgrounds persist beside `canon.yaml` for reuse, Acolyte remains as the one
  SRD row. Kelly holds content veto; ruling assumes her yes.

### Ruled 2026-08-15 (Fable, after the seat-split + P2.6 handoffs — Phase 2 complete)

- **Drift baseline: the fixture, not the seed.** Check recovered-canon fixtures for
  both archived sessions into the repo, stamped with generation metadata (model,
  temperature, date, source-log hash); the drift baseline runs against those
  artifacts. Rationale: seed reproducibility is hostage to model version,
  quantization, and Ollama internals — it breaks silently on the first upgrade —
  while a version-controlled fixture cannot move (the SRD-pin instinct). This also
  splits two tangled measurements: fixture→prompt is *survival* (now
  deterministic); re-sweeping a log and diffing against the fixture is *recovery
  stability*, itself a Phase 7 number. A seed on analysis-context sweeps is CC's
  discretion as a tightener, never a substitute. May ride with the ingest task.
- **P2.6 endorsed throughout.** The read-only analysis principle ("an instrument
  that alters what it measures is not an instrument") is adopted as standing
  doctrine for `analysis/`. The positive-control discipline — refusing to trust a
  zero until the judge caught 3/3 planted contradictions at 0/4 false positives,
  with the verbatim-quote requirement enforced in code — is exactly how a
  measured zero earns belief. The creation-scene replay filter fix approved (an
  interview about a character establishes nothing about the world).
- **Supersession stays deferred, now with evidence.** Zero contradictions in 373
  checks on 43 unaided turns says no inline path is needed on this data. Revisit
  only when cross-session fixtures of the same campaign exist — which the first
  real multi-session campaign will produce naturally.
- **Seat-split session endorsed:** fail-loudly-instead-of-migrate is the right
  posture (a silent migration that defeats the ruling it implements is worse than
  an error); seats named in `cost.seat`/`session_meta` is what makes the split
  measurable; the Brakewater before/after is the ruling validated live. Grouping's
  conservative tuning stands — do not loosen without new evidence, and the honest
  "did not fire tonight" is the right way to report it. Sweep *volume* (16
  proposals from one exchange) stays an open observation: the gate + grouping
  absorb it for now; the trigger to act is the table finding end-of-session
  confirmation fatiguing, not a number in a log.

### Ruled 2026-08-14 (Fable, after the P2.3–P2.5 handoffs)

- **Utility seat split — ruled.** Two seats replace one: `utility_interactive`
  (llama3.1:8b — the sweep and any job the table waits on) and `utility_batch`
  (**llama3.3:70b on toto-llm** — chronicle, fold, future compression). Grounds:
  the jobs have opposite tradeoffs and three measurements now agree — sweep is
  confirmation-gated so the 8B's recall-over-precision is absorbed and 3.7s
  matters; the chronicle is ungated and comprehension-critical, grounding cannot
  catch relationship inversion (Brakewater), and 180s on a batch job is free.
  Config schema change is CC's to implement; models remain data.
- **Chronicle confirmation gate: none — CC's call confirmed.** All three grounds
  ratified; the decisive one is that a reflexive 11pm "yes" is a gate in name
  only, worse than none because it launders output as reviewed. The structural
  protections (separate family that cannot file canon; "recollection, not
  record" subordination; printed at session end; hand-editable data) are the real
  safety, and the seat split raises writer quality at the source.
- **Sweep near-duplicate flood: display-level grouping, not ledger-level
  suppression.** Fuzzy matching is too fragile to silently drop facts
  (npc-village lesson), but clustering visibly-similar proposals at the
  confirmation UI — table confirms one phrasing per cluster — is interface, not
  truth. Wire details CC's; non-urgent, may ride with any later task.
- **P2.2's supersession deferral endorsed** — P2.6 measures live-contradiction
  frequency before a fix is chosen; choosing now would be guessing. The
  `input_tokens=2` non-fix **endorsed with appreciation**: reporting "nothing to
  fix, with evidence" instead of writing an approved fix that would worsen the
  numbers is the correct disobedience, and the pinning test carries the proof.
- **P2.4/P2.5 deviations all approved**: the two-verb tag (a direction word is a
  guessable field, and item movement must not be guessable); the parser
  asymmetry argued from failure cost (canon never loses a fact, inventory never
  guesses an item); `applied` vs `confirmed`; `/inventory` as OD-11 applied to
  gear; the sentence-aware grounding correction over two drifting copies of one
  rule; the fold dropping (not superseding) pre-fold entries — superseded canon
  is drift's measuring stick, a pre-fold summary is just longer text.
- **Scheduling directive: the backgrounds + starting-equipment ingest is the
  task after P2.6, before Phase 3.** Queued nine days; combat is where
  weightless gear and skill-short sheets stop being cosmetic, and the SRD weight
  lookup pairs naturally with P2.4's 0.0-weight gap.

### Ruled 2026-08-10 (Fable, after the Phase-1-close + P2.1 handoffs)

- **OD-16 — log raw, exclude from the campaign cost model.** `would_have_cost` keeps
  being recorded exactly as provider-reported (measurements are never adjusted or
  discarded), but subscription-mode cost figures are declared measurements of the
  *harness*, not the campaign: **all campaign cost claims come from `api` runs
  only.** Caveat recorded in D-008 (amended same day). No engineering effort on the
  per-turn `cache_write` — each `claude -p` is a fresh process whose harness context
  plausibly differs per invocation, so the rewrite is likely inherent, and either way
  it is outside our system boundary. The `input_tokens=2` capture hole: fix approved
  as CC proposed. *(Outcome 2026-08-10: **no fix written — it is not a bug.** Two live
  probes showed the adapter already reads the correct aggregate and the `2` is a true
  measurement of a prompt that is cache-written every turn. Evidence and the pinning
  test are in that day's entry.)*
- **P2.1 contradiction rule ratified: canon-wins, conflict logged.** "A ledger that
  follows the latest narration has agreed with the drift by definition" is the whole
  argument — the claims-ledger lesson in pure form. World changes are supersession
  (deliberate, provenanced); contradictions are model errors, and errors do not
  mutate ground truth. GM-arbitration explicitly rejected (the model that produced
  the error is the wrong arbiter, at extra cost). Door left open, not built: a
  deliberate human retcon someday = an explicit table command performing
  supersession — never automatic.
- **CC's D-008 vocabulary additions ratified**: `conflict` operation,
  `inventory_change` (implements the 08-05 items-are-state ruling),
  `chronicle_write` as a separate family (a lossy summary must not be able to enter
  the ledger as fact — good), and the `CanonScope` doc correction.
- **Phase-1-close deviations approved** (`CommandResult` is the honest signature;
  `/switch` on player names is right for a two-person table). **OD-15
  implementation endorsed** — the test asserting no prompt template mentions
  `/scaffolding` makes the fiction/chrome principle structural, in the OD-12
  tradition. **DC-anchoring watch closed** as an n=3 artifact (12/12/13/14 this
  session); the ladder stays pre-authorized only if anchoring returns.
- Both drift fixtures confirmed on the NAS per the retention rule (Ashmill 08-06,
  Salt Road 08-09) — Phase 2's drift test may proceed against them.

### Ruled 2026-08-05 (Fable, after the first play session — see docs/playtests/2026-08-05-first-play-session.md)

- **OD-15 — scaffolding fade: player-initiated, meta in the chrome.**
  `/scaffolding high|low|off` command; CLI (never GM prose) hints periodically that
  it exists — extends OD-11's fiction/chrome split. No auto-fade: "player ignored
  the options" is fuzzy lexical detection (npc-village lesson); ignore-rate is in
  the logs for Phase 7 to revisit with data. Phrasing-variety obligation added at
  all levels (23/32 identical closings is a formula, not a menu). D-006 amended.
- **Finding 3 (all DCs = 12): watch, fix pre-authorized.** If anchoring persists
  next session, CC may add a DC ladder with worked examples to the prompt without
  a further ruling round-trip. Keep logging `gm_adjudication` as-is.
- **Finding 4 fix (open_scene) approved retroactively** — live-verified per
  protocol; "a world already in motion" is the right opening instruction.
- **Finding 5 (inventory desync) ruled into Phase 2 scope.** Items are state;
  acquisition joins canon extraction: GM proposes via a `[[GAIN/LOSE]]`-style tag
  (the `[[CHECK]]` precedent), player/CLI confirms, engine mutates the sheet, event
  logged. Wire format is CC's call, doc-first per D-008. TASKS.md Phase 2 updated.
- **Finding 1 (world not remembered): no ruling — it is Phase 2's mandate,
  now with a before-picture.** Standing data-retention rule invoked: the Ashmill
  log `logs/20260805-063755.jsonl` must be archived to
  `\\TRUENAS\shared\data\dnd-campaign-logs\` before Phase 2 analysis (logs/ is
  gitignored; the NAS copy is the only retention). Kelly notified. Pre-Phase-2
  sessions are one-shots by nature — set table expectations accordingly.
- Finding 6: cost model confirmed at ~$1.10/3hr extrapolated; no change.

### Ruled 2026-08-05 (Fable, after P1.4 handoff)

- **OD-13 — confirmed.** Allocation by ranking is OD-12's principle applied to
  creation: the judgment is genuinely ordinal, illegal spreads are unrepresentable
  rather than validated, and the GM never sees or states a score. Concepts needing
  unusual spreads get another *named* point-buy shape — the standing "richer
  engineered signal, never restore the integers" remedy. D-005 amended same day.
- **OD-14 — confirmed as a scoped, written exception.** The creation interview may
  keep its own transcript: bounded by completion, history-dependent, discarded
  after, ~$0.05/character measured. Recorded in D-005 explicitly so it is an
  exception with a boundary, not a precedent for play prompts. D-002's rule is
  untouched for play.
- **P1.4 deviations 3–4 approved.** Generalizing `_NarrationStream` to `[[` means
  the next tag cannot leak to a player by omission; reusing `gm_narration` with
  `scene: "character creation"` correctly respects D-008's doc-first rule — the
  scene field is an adequate discriminator for Phase 7 filtering. (Deviations 1–2
  are OD-13/OD-14, ruled above.) The stale `pc_fact` doc comment is queued for the
  next D-008 touch.
- Known issues accepted. **Two data tasks queued for CC** (non-blocking, before
  Phase 2 or alongside it): backgrounds granting their two skills, and starting
  equipment as SRD data — both ingest-scope work, neither blocks P1.5.
- Live-run discipline elevated: per the four-task pattern (fallbacks, canon leak,
  display/continuity, creation×5), **a task with a model-facing surface is not
  done without a live run.** Treat as protocol from here.

### Ruled 2026-08-05 (Fable, after P1.3 handoff)

- **OD-12 — structural withholding confirmed and ratified.** Not merely permitted:
  it is the correct reading. Protection by construction over protection by
  instruction (the mystery's cover-substitution lesson applied to numbers) — a rule
  the model must remember on turn 90 eventually fails; a rule enforced by what
  enters the prompt cannot. Governing principle added for Phase 3+: **if the GM
  appears to need raw numbers, the boundary is misdrawn** — legitimate GM judgment
  is always ordinal/categorical ("one hit from down", "most hurt", "escalate now"),
  computable as a deterministic engineered signal; the remedy for a combat gap is a
  richer severity vocabulary or moving the decision into the engine, never
  restoring integers. (5e's own "bloodied" is precedent that categorical is the
  native GM-facing representation.) D-001 amended same day.
- **P1.3 deviations 1–4 approved.** Special note on finding 3 / deviation 1:
  catching that P1.1's backend-minted `call_id` could not satisfy OD-9's
  pending-row pairing — and fixing to caller-minted with adapter echo plus a
  `failed` terminal row on crash — is the ruling actually implemented rather than
  nominally implemented. `rules/severity.py` as a deterministic module is exactly
  where OD-12 wants that logic to live; adjudication-after-resolution write order
  accepted (exact linkage beats logical order in an append-only log, no crash
  window between them).
- Known issues accepted. `MAX_GM_CALLS = 2` specifically endorsed — an unbounded
  narration loop is a prompt bug that would spend real money discovering itself;
  sticky active player over rotation is right for exploration.

### Ruled 2026-08-05 (Fable, after P1.2 handoff)

- **OD-11 — ruled: option (c), qualitative narration only.** The GM never restates
  engine-resolved mechanical values (damage, HP, roll totals, DCs, modifiers) in
  prose; the CLI renders them authoritatively from state beside the narration —
  one numeric source of truth, no transcription-desync side door. Two scoping
  refinements: (1) narrative-world quantities ("three goblins", "fifty gold")
  remain legal story facts — the ban covers engine state only; (2) the prompt owes
  a **severity-fidelity** clause — with numbers removed, prose is the felt sense of
  magnitude and must track it proportionally. D-001 amended same day. Implementation
  lands with P1.3 (prompt clause + CLI mechanical-result display).
- **P1.2 deviations 1–4 approved.** The `system`/`system_volatile` cache split now
  rather than after Phase 2 built a consumer on the wrong seam; `[[CHECK: ...]]`
  specified in P1.2 is correct — it is prompt content and the wire format is now
  documented where both tasks can see it; `--show-prompt` running before any
  billing/backend construction is the right dependency order for a debugging tool;
  the rich-markup fix (P1.1's streaming would have eaten `[[CHECK]]` as a style
  tag) is another live-call catch — pattern noted.
- Known issues accepted (chronicle deferred to Phase 2 as designed; CLI-flag
  context until P1.3 wires campaign state; 229-token scaffolding delta is an
  acceptable per-turn cost at `high` and will fall as D-006 fades it; scope-order
  rendering is what makes the prefix cacheable — good).
- Noted with appreciation: Finding 2 (true-is-not-known leak, caught live, ruled
  into the prompt, pinned by test) is the project's research thesis validating
  itself in week one — and the unmarked-hidden case failing while the GM-only
  secret held is a Phase 4/7 result in embryo. Preserve both transcripts.

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

## 2026-09-03 (g) — Phase 6 opens: one loop, two front ends (Claude Code, kelly-pc)

**Phase 6 planned and P6.1 done.** 1389 tests, suite still fully offline. Kelly confirmed
the P5.5 backfill was fine ("we'd probably start new character sheets anyway") and said to
proceed.

### The rule the phase is built on

Phase 6 puts a browser in front of the same campaign the CLI plays, and the tempting way
to do that is to write a second turn loop in the web layer. It is the wrong way for
exactly the reason a save point holds nothing the ledger owns (P5.1): **two authorities
for one behaviour drift the first time one path changes and the other does not.**

Here the drift would be silent and expensive. The web loop would forget to record a save,
or to confirm an item, or to close the session — and the campaign it produced would be
subtly not the campaign the CLI produces, in a project whose entire purpose is measuring
whether a campaign stays consistent with itself. So: **one loop, two front ends**, and the
loop is `game/session.py`.

### What P6.1 actually moved

`_cmd_play` was doing four separable jobs at once: building a session, running turns,
asking the table things, and drawing on a terminal. The first two are now `PlaySession`.
The last two are a `Table` the caller passes in — `rich` today, a browser from P6.3.

**The protocol is about questions and answers, not widgets.** Nothing in the session knows
what a panel looks like. It knows that after a turn somebody must be shown what happened,
and that before an item reaches a sheet somebody must say yes. Those are true at a table
regardless of what the table is looking at, and they are precisely what a second front end
must not be free to skip. A test pins `ConsoleTable` as a conforming implementation, so if
a later task adds a method to the protocol the terminal has to answer it too rather than
the two drifting apart in silence.

**The end-of-session jobs reach the table through the protocol rather than running in the
session**, because the sweep and the chronicle are `rich`-built confirmation flows and
untangling those is P6.5's whole task. But their **ordering moved into the session**,
because "sweep, then chronicle, then close the save, then say what it cost" encodes a
decision — an interrupted end-of-session should lose the summary, which regenerates for
free, and not the canon, which does not — and a front end must not be able to get that
wrong by writing its own sequence.

### The other Phase 6 decisions, made now rather than discovered later

**No build step.** Server-rendered HTML, SSE, vanilla JS. A house LAN app that needs
`npm install` to move a button is a worse instrument, and this repo has no JS toolchain to
protect. `fastapi` and `uvicorn` will arrive as an optional `web` extra so the rules core,
the CLI and the whole suite still run without them — the posture `anthropic` already has.

**The read-only mirror (P6.3) comes before the write path (P6.4).** It has value on its
own — Sam's phone showing the scene while Kelly plays hot-seat — and it forces the
secrecy boundary into existence before there is any concurrency to confuse it with.

**P6.2 is a task rather than a line of P6.3.** A browser is the first surface where a
`gm_only` fact reaches a device the GM is not holding, and the answer has to be the P4.1
one: absent from the type, not filtered from it. That deserves its own tests and its own
name.

### Deviations

- **Party loading stayed in the CLI.** `_gm_campaign_context` prints its own errors and is
  argparse-shaped; moving it would have grown this task without serving it. The web will
  either reuse it or get its own loader in P6.4, and the choice is better made when there
  is a caller to make it for.
- **Two small behaviours were preserved deliberately rather than accidentally**: a failed
  turn still gets no scaffolding hint and no trailing blank line, because nothing was
  narrated to react to. The first version of the refactor lost both — the old code got
  them from a `continue`, and the tests did not cover either.
- `_speaking` is gone; the narration object now owns flushing the stream before an NPC
  speaks, which is where that belonged.

### Known issues

- **`PlaySession` still takes its parts pre-built.** Which backend, seat and log a session
  runs on is a front end's decision, so `start()` accepts them rather than constructing
  them — but that means the web must assemble the same six objects the CLI does, and
  nothing yet stops it assembling them differently. `build_engine` is the piece that
  matters most and is already shared.
- **The `Table` protocol will grow in P6.5.** The confirmation methods it needs
  (`choose_proposals`, `confirm_background`, the recap's scene question) are still called
  directly out of `rich` inside `_run_sweep` and `_run_chronicle`. The conformance test
  will catch the CLI, but the protocol as it stands is not yet the whole surface.
- **Nothing has been served over HTTP yet.** P6.1 is a refactor with no new capability;
  its entire justification is the three tasks after it.

### FOR DESIGN

None new. Nothing ruled is unbuilt.

**Carried, all four still open and none blocking:** the change-of-mind trigger; whether the
GM should voice player characters; whether a `blocked` line should cost the turn; and
whether a closed save should restore the turn window.

One question Phase 6 will raise for real and does not need answering yet: **on a house LAN
with no auth, any browser can claim to be any player.** P6.4 will implement identity as a
choice made on connect and stored in the browser, and write down plainly what that does
and does not protect. If Kelly wants something stronger than "we trust everyone on the
wifi", that is a ruling worth having before P6.4 rather than after.

### Recommended next task

**P6.2 — the view model**, per TASKS.md. It is the boundary every later task sits behind,
and it can be written and tested with no server at all.

Still outstanding and still not code: **an evening with Kelly and Sam at the Brakewater
crossroads.** Phase 6 exists to make that evening better; it is not a substitute for
having had one.

---

## 2026-09-03 (f) — P5.5: a name is not evidence (Claude Code, kelly-pc)

**P5.5 done.** 1364 tests, suite still fully offline. The second task running needing **no
D-008 amendment** — no new event family, no new fields, nothing about the log changed.

The (e) handoff recommended Phase 6 and flagged the chronicle pronoun bug as worth doing
first. I measured it before starting, and both halves of what that handoff said about it
were wrong in ways that changed the work.

### What the logs actually say

Across all fourteen logs, restricted to sentences naming exactly one player character and
no other person:

| | she/her | he/him | they/them |
|---|---|---|---|
| Corin Vale | **5** | 0 | 0 |
| Brother Hammond | 0 | **10** | 0 |

**The GM was never the problem.** In play it has been right every time. My first pass at
this measurement said otherwise — 7 masculine references to Corin — and that number was an
artifact of a 120-character window that swept up the guard's pronouns from the same
sentence. Worth recording because the corrected number is the one that identified the real
culprit, and the wrong one would have sent me to the GM prompt.

The chronicler is the problem, and its position explains why: it reads a transcript with no
roster, so **the name is the only evidence it has.** That is also why the failure is uneven
rather than random. "Brother Hammond" carries the signal a guess is made from; "Corin Vale"
does not. A guess that works on one name and fails on another does not look like a bug — it
looks like reliability, right up until the person it fails on is the one at the table.

### The handoff's other claim was simply false

It said "the sheets carry pronouns; the prompt does not get them." `NPCProfile.pronouns`
has existed since P4.1. **`CharacterSheet` never had the field at all.** So co-creation
never asked, nothing was ever recorded, and no prompt change could have fixed it — the fix
was not plumbing, it was that the answer did not exist anywhere in the system. Every layer
was re-deriving it from prose, which works exactly as well as the prose it is given.

### What changed

`pronouns` is now free text on `CharacterSheet` and `Concept`, asked for in co-creation
(`pronouns` / `pronoun` / `gender` all parse), and carried on `PartyMember` into the GM's
party block every turn. The **cast** block gained it too, which was an unrelated find of the
same shape: `npcs.yaml` has recorded pronouns since P4.1 and the GM was never shown them,
so it has been directing a they/them caravan master with nothing but the name to go on.
Chronicle, fold and recap prompts all now say to use what they are given and, where a name
has none, to repeat the name rather than choose.

**Blank stays blank the whole way down.** A default of "they/them" would be a guess wearing
a safer coat, and the point is to stop guessing, not to guess more politely.

**NPC pronouns reach the chronicler only for names the session already said.** The
grounding vocabulary is built from the transcript, so a cast list rendered into that prompt
would widen what the chronicler is permitted to name — the check writing its own permission
slip. This is the P4.1 discipline on a fourth surface, and the test asserts the excluded
name appears nowhere in the assembled prompt, not merely that it was filtered.

### Verified live, four runs each way

Replayed the real 11-turn session-2 log through the chronicler on toto-llm, with the field
and without, and **read all eight paragraphs by hand rather than trusting a regex.**

- **Without: 3 of 4 misgendered her.** *"He found a gap in the load of one wagon"*, *"he
  attempted to deflect the guard's suspicion"*, *"When the guard didn't believe him"*.
- **With: 0 of 4.** *"She found a gap… her investigation was cut short by the guard, who
  became suspicious of her actions… the guard saw through the lie and confronted her"* —
  and *"Corin Vale attempted to deflect **his** attention"*, which is the guard, correctly.

The hand-reading was not ceremony. My first detector reported **4/4** because it flagged any
masculine pronoun in a sentence containing "Corin", and in this scene almost every such
sentence also contains a he/him guard: *"confronted Corin, who tried to brush him off"* is
correct English about the guard and was scored as a failure. 3 of 4 is the number that
survived reading. The instrument that overcounts in the direction of the finding you want is
the one to distrust hardest, and P5.4 spent a whole task on that principle for money.

### Known issues

- **The two Salt Road sheets were backfilled from the logs, not from the names** — Corin
  she/her (5 clean references, none contrary), Hammond he/him (10, none contrary). That is
  evidence rather than inference, but it is still me deciding for two characters I do not
  play. **Kelly and Sam should confirm or change both**; it is one line each in
  `campaigns/the-salt-road/characters/*.yaml` and `dndc sheet show` prints it.
- **Existing chronicle entries are not rewritten.** `chronicle.yaml` is hand-editable data
  and any entry that already misgenders somebody stays wrong until edited or regenerated. I
  did not touch the campaign's own file — nothing this session wrote into
  `campaigns/the-salt-road/` except the two pronoun lines.
- **The fold inherits whatever the entries already say.** A pre-fix paragraph compressed
  after the fix carries its old pronouns in as source text, and the prompt's instruction can
  only fight that so far.
- **Nothing checks pronoun consistency automatically.** The measurement above was a
  throwaway script. As a Phase 7 instrument it would be a genuine one — a per-character
  pronoun-consistency rate over a campaign's logs is exactly the kind of number this project
  exists to produce, and it now has a clean before/after to calibrate against.

### FOR DESIGN

None new. Nothing ruled is unbuilt.

**Carried, all four still open and none blocking:** whether a GM should declare a change of
mind before the character concedes it; whether the GM should voice player characters at all;
whether a `blocked` line should cost the turn; and my own (b) question, whether a closed save
should restore the turn window.

### Recommended next task

**Phase 6 — the LAN web GUI**, per TASKS.md: FastAPI over the same engine, two-device play
from the couch, hot-seat CLI still supported. Phase 6 has no task breakdown yet; the session
that starts it should write one first, as Phase 5's did.

Still worth doing alongside it: **a playtest doc for Phase 5**, if the next session is a real
one — `docs/playtests/` has nothing about persistence, the recap, or the cost report,
because none of it has been through a real evening.

And the thing that has been top of this list for five sessions: **an evening with Kelly and
Sam at the Brakewater crossroads.** Nothing is blocked, nothing ruled is unbuilt, and the
one question this session answered was answered by measuring an evening that already
happened — which is a poor substitute for another one.

---

## 2026-09-03 (e) — P5.4: what an evening costs, and the two currencies it costs it in (Claude Code, kelly-pc)

**P5.4 done. Phase 5 is complete.** 1338 tests, suite still fully offline. The first task
in the phase that needed **no D-008 amendment** — `cost` rows have carried everything this
needs since P4.5 added `latency_ms`, and nothing had ever read them back.

No model calls anywhere in the task, which meant it could be verified against **fourteen
real sessions** instead of fixtures. That is the nicest kind of verification available and
it is worth noticing when a task offers it.

### Three rules, all of them about a total not claiming more than it knows

**Money and would-have-cost never add.** In subscription mode `usd` is what the call *would*
have cost at API rates, and OD-16 already ruled that those figures measure headless Claude
Code's harness rather than this campaign. So they get their own column, their own line, and
the words *not a bill, and not comparable*. Adding them would produce a number that is
wrong in a way nobody could later detect.

**A local seat's cost is time.** toto-llm bills nothing and can hold the table up for a
minute. A report printing `$0.00` beside the 70B and stopping would be lying by omission —
the expensive thing about the NPC tier has never been money. Latency sits beside spend, as
**median and worst case** rather than a sum: one 62-second cold load inside twenty warm
calls is the finding, and a mean hides it exactly.

**Unpriced calls are counted, not zeroed.** A row with no price is a local seat or a model
missing from `pricing:` in config.yaml. The second one is a bug, and a total that silently
skipped it would under-report forever, so the report says the figure is a floor.

### What it says about this campaign

```
cost - The Salt Road · 14 sessions
  seat   calls      in      out   median  slowest     spend
  gm        41  21,367   18,980     9.5s     9.5s   $0.2428
  npc        1      25        2   1m 05s   1m 05s     local
  $0.2428 billed · 1 local call, 1m 05s of it waiting
  ($1.6617) would have cost that at API rates — not a bill, and not comparable (OD-16)
```

**Twenty-four cents of API spend across the whole campaign to date** — and that figure needs
its denominator said out loud, or it flatters the project. Those fourteen sessions are
mostly verification runs of two to four turns, not evenings; the two real playtests are in
there but so are a dozen smoke tests. Per call it works out around $0.006, which is exactly
consistent with the plan doc's measured **$0.50–2 per 3-hour session** (2026-08-04,
superseding the original estimate) and with the 08-05 playtest's ~$1.10 for three hours.
**Nothing here revises the cost model; it confirms it from a second direction.** The single
local call at 1m 05s is the 70B's cold load, measured rather than remembered — the point of
`latency_ms`, and the lesson of 2026-09-02 (e), where a timing claim was answered from
memory and was wrong.

`dndc cost` reads the newest session; `--log` any of them; `--campaign` the campaign to
date, by slug or by name. The same report prints at session end.

### One thing fixed on the way

`"gm"` was a bare string literal in four places while `npc`, `utility_interactive` and
`utility_batch` were constants — with a comment beside them saying why: *the split is only
measurable if both halves of the codebase spell it the same way*. In the task whose entire
job is measuring that split, that comment is not decoration. `GM_SEAT` now exists and is
used.

### Known issues

- **The pre-P4.5 logs have no latency at all**, so a campaign-to-date median is drawn only
  from sessions since 2026-09-02. The report shows `-` rather than `0`, which is honest,
  but a Phase 7 trend line over latency starts in September and not in August.
- **Subscription-mode token counts are not comparable either.** Session 2's log records 22
  input tokens for eleven turns, which is the harness reporting its own accounting rather
  than the campaign's. OD-16 says this about cost; it is equally true of tokens, and the
  report currently displays them without the caveat the money gets.
- Nothing dedupes a campaign's scratch logs. `--campaign` filters by the name in
  `session_meta`, so verification runs under other names are excluded — but a scratch run
  *under the campaign's own name* would be counted. Nothing to do until it happens.

### FOR DESIGN

None new. **Phase 5 is complete and nothing ruled is unbuilt.** The (b) question stands —
should a closed save restore the turn window — still my call, still one boolean.

**Carried, all three still open and none blocking:** whether a GM should declare a change of
mind before the character concedes it; whether the GM should voice player characters at all;
whether a `blocked` line should cost the turn.

### Recommended next task

**Phase 6 — the LAN web GUI**, per TASKS.md: FastAPI over the same engine, two-device play
from the couch, hot-seat CLI still supported. It is the first phase whose value is entirely
about how the table *feels*, which makes it the phase most in need of the thing below.

Two smaller things worth doing before or alongside it:

1. **The chronicle pronoun fix** from (d) — the chronicle called Corin "he". The sheets have
   pronouns; the prompt does not get them. A prompt change and an evening's work, and it is
   read aloud now.
2. **A playtest doc for Phase 5**, if the next session is a real one: `docs/playtests/` has
   nothing about persistence because none of it has been through a real evening.

And the thing that has been top of this list for four sessions: **an evening with Kelly and
Sam at the Brakewater crossroads.** Phase 5 is done. The evening survives being interrupted,
picks itself back up, reads itself back to them, and tells them what it cost. There is
nothing left to build before that table happens.

---

## 2026-09-03 (d) — P5.3: the campaign read back to the people who played it (Claude Code, kelly-pc)

**P5.3 done.** 1311 tests, suite still fully offline. Live on toto-llm against a chronicle
written from the real session-2 log: **10.6 s, one call, grounded, and the scene it
proposed was the right one.**

### What a recap is, given the chronicle already exists

They are not the same artifact and the difference is worth stating once. A **chronicle
entry** is written for the GM's prompt: stored, phrased as a record, and read by a model in
every later session. A **recap** is written for Kelly and Sam, out loud, in the half-minute
before the first turn — and it is kept nowhere at all. It is generated fresh at pickup and
thrown away when it has been read.

So `recap` is its own event family (D-008 item 28) rather than another `chronicle_write`.
They differ in audience, lifetime and authority, and counting recaps as chronicle entries
would corrupt the one measurement the third memory layer exists to support: how much prose
the GM is carrying, and from how many sessions.

### Two properties, both structural rather than instructed

**It writes no canon.** The recapper is handed no store and has nothing to write with, so
the read-only rule in the task line is a fact about the object rather than a sentence in a
prompt. A recap that could file canon would be a fourth memory layer nobody ratified — and
the worst of the four, since it is the only one summarising summaries rather than play.

**It is never told anything the players do not know.** It gets the chronicle plus
`player_known` and `character` canon, and nothing else. `gm_only` never comes near it, and
neither does world canon — *the ledger is the world, not the party's notes*, and a fact
being true does not mean anybody has found it. This is the P4.1 discipline on a second
surface, and the argument is sharper here than for an NPC: a leak into a character's line
is a slip the gate might catch, but a leak into a recap is **announced to the table** by
the person reading it out. Asserted on the assembled bytes, in a test and again in the live
run (`secrets in the record handed to the recap: none`).

### The scene proposal, which is what makes the call worth making

Without it a recap is a slower reprint of `chronicle.yaml`. With it, the job answers the
question the record could not: **where is everybody standing?** `campaign.scene` is written
only by `--scene` and `/scene`, so it goes stale the first time the party travels and
nobody remembers to type — the known issue from (b) and (c), now closed.

One call returns both halves (`PREVIOUSLY:` / `WHERE:`), and the two degrade differently on
purpose. An unlabelled reply is still shown as the recap; a scene sentence picked out of
the wrong place is **not** used, because prose the table did not need costs them ten
seconds and a wrong scene starts the whole evening in the wrong room. The prompt is told to
answer `WHERE: unknown` rather than guess, and that is taken literally. The table confirms
before it is used; refusing changes nothing.

### Live

Chronicle written from the real 11-turn session-2 log (81 s on the 70B), then the recap
over it plus the campaign's six player-known facts:

> **PREVIOUSLY:** You had just arrived in Brakewater, a waystation town on the edge of the
> salt flats, where a commotion at the crossroads caught your attention — a caravan guard
> was accusing a teamster of stealing a crate from one of the wagons. […] The situation was
> left unresolved as the evening drew to a close.
>
> **WHERE:** You are standing at the crossroads in Brakewater.

Which is exactly where that evening stopped. 10.6 s warm, one call, nothing invented.

It also runs **before** the NPC tier is built, which means the 70B's cold load is paid by a
call the table actually wanted rather than by `warm_up()`'s throwaway — same model, same
host, so the warm-up that follows finds it resident. That is what the ordering is for; it
was not separately measured tonight.

### Known issues

- **The recap inherits whatever the chronicle got wrong, and this run showed it.** The
  chronicle called Corin Vale "he" ("before *he* could investigate further"); she is
  referred to as "she" throughout the playtests. Grounding cannot catch that — every name
  in the sentence is real — and it is the same class of failure that motivated putting the
  chronicle on the 70B in the first place (Fable, 2026-08-14). The recap happened to avoid
  pronouns and so did not repeat it, which is luck rather than design. **The fix belongs in
  the chronicle prompt** (give it the party's pronouns, since the sheets have them), not
  here, and it is worth doing before the chronicle is read aloud to the people whose
  characters it is describing.
- The recap's last sentence drifted a little into inferring intent ("You were still trying
  to figure out…"). Harmless, arguably useful, but it is not in the record.
- Nothing caches the recap. Starting a session twice in an evening pays for it twice; at
  ten seconds that is not worth solving.

### FOR DESIGN

None new. The (b) question stands — should a *closed* save restore the turn window — still
my call, still one boolean, still non-blocking.

**Carried, all three still open and none blocking:** whether a GM should declare a change
of mind before the character concedes it; whether the GM should voice player characters at
all; whether a `blocked` line should cost the turn.

### Recommended next task

**P5.4 — the session cost report**, which finishes Phase 5: per-seat totals, call counts and
latency read back from the log's `cost` rows, at session end and as `dndc cost`. The seat
split was made to be measurable (Fable, 2026-08-14) and this is the thing that measures it.
The `recap` and `belief_change` rows added this week both carry seat and latency already.

Then **the chronicle pronoun fix** above, which is a prompt change and an evening's work,
and is the sort of thing the table will notice before any instrument does.

Still the only thing that needs a human: **an evening with Kelly and Sam at the Brakewater
crossroads** — where, as of tonight, the machine now knows they are standing.

---

## 2026-09-03 (c) — P5.2: the two places a restart could still lie (Claude Code, kelly-pc)

**P5.2 done.** 1290 tests, suite still fully offline. The mechanism landed with P5.1 and
was live-verified then, so this was the short task the last handoff predicted: not building
the rider, but checking the two places it could still be wrong.

### The analysis side was quietly lying about provenance

`replay()` read `session_meta` and assigned each field as it went. That was correct for
every log written before yesterday, because there was only ever one such row. Since P5.1 a
resumed session writes a **second** header into the same file — so the last one silently
won, and an evening that spanned a crash reported one `commit_sha` for turns that had run
under two.

That is the one field in the log that exists to answer "which code produced this", and it
was answering with whichever code happened to *finish* the evening. Now:

- `commit_sha` — what the session **started** at, never overwritten.
- `commits` — every distinct commit that wrote into the log, in order.
- `restarts` — how many times the process came back. Zero for every log before today.
- `resumed_from` — what this session was picked up from, when it was.

Nothing else in `analysis/` needed changing: `replay_turns` concatenates whole sessions, the
drift baseline pins its own provenance, and the abandoned call at the crash point was
already handled — a `pending` row with nothing terminal is not a turn, which the module
docstring has said since P2.6.

### The resume is now driven through `dndc play`, not through the store

The P5.1 tests exercised `SaveStore` and `restore()` directly, which proves the parts and
not the wiring. These kill a session for real — a `RuntimeError` raised after a turn has
been saved, which is what a process dying between one turn and the next prompt actually
looks like — and then resume it:

- the save left behind is open, with the opening scene and the killed turn in it;
- the second run writes into the **same log file** and `seq` runs `0..n` unbroken;
- the pre-crash narration and player input are in the GM's assembled prompt on its first
  call, which is the property that matters — the GM cannot tell the process restarted;
- `--fresh` starts a new log and the old scene is *not* in the prompt;
- and a session that ended properly starts a new log next time, because a bedtime is not
  a restart.

**Verified against a real artifact as well**, not just fixtures: replaying yesterday's
actual crash log gives `restarts 1`, `resumed_from` naming the previous evening, and 2
turns rather than 3 — the abandoned call correctly not counted. It also shows the
`dirty_worktree` flag earning its place: both halves ran at `56ba1cc` with uncommitted P5.1
code in the tree, so the SHA alone does not describe what ran, and the flag is the only
thing that says so.

### Deviation, made deliberately

**A failed model call mid-loop used to end the process with a traceback.** Only the opening
scene was guarded. Since the entire claim of P5.1 and P5.2 is that an interruption does not
cost the evening — and a rate limit or a dropped connection is the likeliest interruption
there is — the turn loop now catches it, says what failed, and hands the turn back to the
table. `KeyboardInterrupt` is not an `Exception` and still ends the session cleanly, so
Ctrl-C keeps working exactly as it did.

This is scope I added rather than scope I was given, and it is a behaviour change to the
play loop; flagged here rather than buried. The engine's own logging is unaffected — a
failed call still leaves a `pending` row with no terminal, which is what a failed call is
supposed to look like.

### Known issues

- Unchanged from (b): nothing updates `campaign.scene` as play moves, so a restored scene
  is only ever what `--scene` or `/scene` last set. **P5.3 is where to fix it.**
- The retry after a failed turn re-sends the same prompt from scratch; there is no backoff
  and no automatic retry. At a table with a human at the keyboard that is the right shape,
  but it means a rate limit answers instantly and repeatedly if they keep hitting enter.

### FOR DESIGN

None new. The (b) entry's question stands — should a *closed* save restore the turn
window — and is still my call rather than a ruling, still one boolean, still non-blocking.

**Carried, all three still open and none blocking:** whether a GM should declare a change
of mind before the character concedes it; whether the GM should voice player characters at
all; whether a `blocked` line should cost the turn.

### Recommended next task

**P5.3 — recap on the utility tier.** "Previously on…" generated from the chronicle and the
session's own canon, printed when a campaign is picked up again, read-only over the record.
It is also where the stale-scene issue above wants to be solved: a job that reads the
session back can *propose* where the party is standing, confirmed rather than assumed, the
same way the sweep proposes canon.

Then **P5.4** (session cost report), which finishes the phase.

Still the only thing that needs a human: **an evening with Kelly and Sam at the Brakewater
crossroads.**

---

## 2026-09-03 (b) — P5.1: the evening that stops rather than ends (Claude Code, kelly-pc)

**Phase 5 opens.** It had no task breakdown, so it has one now (P5.1–P5.4 in TASKS.md),
and the first of them is done. 1281 tests, suite still fully offline.

### What Phase 5 turned out to be about

Everything durable already had a file and a writer — canon in `canon.yaml`, sheets in
`characters/`, backgrounds in `backgrounds.yaml`, past sessions in `chronicle.yaml`. What
was lost at the end of every session was the part nobody had named: **where the party is
standing.** The scene, the turns still inside the prompt window, whose seat it is. Quit
mid-scene and the campaign remembered every fact about the world and nothing about the
moment.

So the phase's governing rule is that **a save point stores only what nothing else owns.**
Canon, sheets and chronicle are deliberately absent, and the absence is asserted on the
written bytes rather than trusted — the same test shape the NPC prompt uses. A copy of the
ledger in here would be a second authority for the same fact, and two authorities drift
the first time one path writes and the other does not.

### What was built

`schema/save.py` + `game/saves.py`, written to `campaigns/<slug>/saves/state.yaml`
(gitignored, hand-editable, atomic like a character sheet). D-008 amended first, item 27:
`session_meta.resumed_from` and `resumed_turns`. A **field, not a family** — resuming is
not something that happens during a session, it is a fact about how the session started,
and that is what `session_meta` is for. The save itself emits nothing at all: it is state,
not history, and it is the one file in this project that gets rewritten rather than
appended to, which is precisely why it holds nothing the append-only log is the record of.

### The design call, and it is the whole task

**`closed` is the difference between a crash and a bedtime.**

An **open** save is a session that stopped. The window comes back whole, and the run
continues *that session's own log* — `SessionLog.open` picks `seq` up from the highest
already on disk, which is the npc-village rider finally doing the job it was ported for.
An evening interrupted by a crash lands in the record as one session, not two halves.

A **closed** save is a session that ended properly: the sweep and the chronicle have run.
It restores the scene and **not** the turns. D-002 is explicit that a past session reaches
the prompt as chronicle prose, and replaying its raw turns on top of the summary of those
same turns is the growing-transcript failure the three layers exist to prevent. It also
lets the GM open a new session properly, which is what a table would expect after a week
away.

Two smaller calls fell out of it. An explicit `--scene` beats whatever the save remembers,
because somebody typing one is deliberately moving the party. And the acting player is
checked against the party rather than trusted: a save can outlive the character it names.

### Live, and what the crash actually showed

Verified end to end on the API seat against a scratch campaign, deleted afterwards.

- **Bedtime path:** session one ended normally; session two announced *"picking up where
  the last session left off (2 turns)"*, opened a fresh scene at the same ford with no
  `--scene` given, and its `session_meta` carried `resumed_from` and `resumed_turns=2`.
- **Crash path:** a session was killed with `taskkill` mid-scene, leaving an open save.
  The next run announced *"resuming session 20260903-060842 — 1 turns"*, wrote into the
  **same log file**, and the GM's reply continued the ford scene a dead process had
  written — the boy in the water, the carter with his rope. One record, `seq` 0 to 14
  unbroken, with a second `session_meta` at seq 6 naming its own resume and its own seed.
- The killed turn is still in that log as `player_input` at seq 4 and a `gm_narration`
  **`pending`** at seq 5 with nothing resolving it. That is D-008's log-intent-before-the-
  call discipline showing a crash exactly as it was designed to: the hole is visible and
  reconstructable rather than silent.

**One bug found on the way, and it was pre-existing.** Session ids are second-resolution,
so two runs started inside the same second shared a log file. Harmless before this task;
after it, a *new* session landing inside an old one is indistinguishable from a restart
that never happened, which is the exact confusion P5.1 exists to remove. `SessionLog.open`
now suffixes (`-2`, `-3`) when it is asked for a new session and the file is taken. A test
caught it, by starting two logs faster than a human could.

### Known issues

- **Nothing updates `campaign.scene` as play moves.** It is only ever what `--scene` or
  `/scene` last set, so a restored scene can be a session out of date — the save persists
  a field the table has to maintain by hand. It works (the ford came back correctly), but
  "where the party is standing" is currently a human's job. **P5.3's recap is the natural
  place to fix it**: a job that reads the session back could propose the new scene the
  same way the sweep proposes canon, confirmed rather than assumed.
- **A crash *during* the sweep or chronicle leaves the save open**, so the next run
  resumes and will offer to sweep the same session again at its end. Confirmation-gated,
  so a human sees it; not worth code before it happens once.
- The save is per-campaign and singular. No "save as", no branch, no undo. Deliberate for
  a two-player home table, and a bad thing to guess at.

### FOR DESIGN

**Non-blocking, and it is my call rather than a ruling — flagged for the record.** Should
a closed save restore the turn window? I have said no, straight off D-002: the chronicle
is the layer that carries a past session, and restoring the raw turns it summarises would
put the same evening into the prompt twice, in two forms, which is what the three layers
were designed to stop. The cost is that a campaign picked up a week later opens on a fresh
GM scene rather than continuing mid-conversation — better fiction most of the time, but if
the table stops mid-sentence and comes back the next night, they will notice. It is one
boolean if Fable disagrees.

**Carried, all three still open and none blocking:** whether a GM should declare a change
of mind before the character concedes it (from the entry below); whether the GM should
voice player characters at all (from (g)); whether a `blocked` line should cost the turn
(from (d)).

### Recommended next task

**P5.2** is mostly proved already — the seq rider is implemented, exercised and
live-verified above — so it is a short task: assert it through the CLI rather than the
store, and check the analysis side reads a two-`session_meta` log without double-counting.

Then **P5.3** (recap on the utility tier), which is where the stale-scene issue above
wants to be solved.

Still true, and still the only thing that needs a human: **an evening with Kelly and Sam
at the Brakewater crossroads.** Phase 4 is complete, and now a session that gets
interrupted survives being interrupted, which makes a real evening cheaper to attempt.

---

## 2026-09-03 — P4.6: minds change decisively, and the GM would not change one (Claude Code, kelly-pc)

**P4.6 done. Phase 4 complete.** 1259 tests, suite still fully offline. The machinery works
end to end on the real seats; the finding is that the GM never asked it to.

### What was built

`[[BELIEF: <name> | <what they now believe>]]` — the ninth use of the tag convention, and
the second that costs a second model call. It declares a **change of mind**, as against
`[[CANON: npc_belief (...)]]`, which declares that somebody **learned something**.

Two tags rather than one flag, on the `[[GAIN/LOSE]]` precedent. Which of the two a
sentence describes is not recoverable from the sentence — *"he now believes the crate never
left the wagon"* reads identically either way — and a character can perfectly well acquire
a belief without abandoning any. Guessing wrong in one direction loses canon; in the other
it leaves a character holding two contradictory stories and saying whichever the sampler
reaches first, which is the exact failure P4.6 exists to remove.

The tag establishes the belief on the GM's own authority. What it **retires** is judged
separately: every standing belief of that character goes to a second call on the gate's
seat, and each one the new belief replaces is superseded through the ledger with
`source: stance`. `retire()` was added beside `supersede()` because one change of mind can
retire several beliefs, and minting a copy of the same sentence per retirement would file
one thought three times.

**Why a second call at all**, when the GM is right there having just written the change:
the canon block in the GM prompt renders facts as prose, without ids — `- [the caravan
guard believes] The teamster took the crate.` The GM has no handle to name. Putting ids in
front of it would rebuild the most load-bearing block in the system so a narrator could do
bookkeeping.

**The pass runs before anyone speaks.** A guard turned around in the same reply that hands
him the floor has to answer from the new mind; retiring the old belief after he has spoken
means the table hears the contradiction first and the correction a turn later.

**It fails open by retiring nothing** — the behaviour every phase before this had — and a
`belief_change` row keeps *ran and retired nothing* distinct from *never ran*, which is the
`unchecked` argument again. `considered` minus `retired` is what the judge saw and left
standing.

### The control caught three things, and only one of them was the judge

`dndc npc stance <name> --campaign the-salt-road`, against the campaign's own standing
beliefs. Final: **4/4 retired that should be, 0/13 retired that should not**, over six runs
(one run scored 3/4 — recall wobbles at temperature 0, worth knowing).

**1. The judge retired on relatedness, not conflict.** First run: "the teamster is
frightened" retired "certain the teamster took the crate". Frightened and guilty are
perfectly compatible. Rules added: a reason to doubt is not a change of mind, an
intensification is not a replacement, and the length of the list is not evidence.

**2. The control caught the author, for the third session running.** A clean case —
"the flap was already loose before the stranger touched it" — was retired, and the judge
was **right**. The loose flap is precisely what Corin is accused of lying about, so
believing it *is* accepting her account, and "she is lying to me" cannot stand beside it.
The fixture was wrong and was replaced (the reason is written into the file beside it).
(f) was my leak vector, (g) was my voice card, this is my control case. **The machinery has
been right and the authored material wrong three times in a row**, which is starting to
look like the shape of this project rather than a run of luck.

**3. Four prompt revisions could not fix the last false retirement; a structural change
fixed it in one.** The teamster's only belief ("he did not take it and cannot prove it")
was retired by "the guard will not listen to him whatever he says" — reproducibly, three
runs, with the judge's own reason reading *"he no longer thinks proving it is an option"*.
Four increasingly explicit prompt rules did nothing. What worked: **every retirement must
quote the words in the old belief that the new one contradicts, and an unquoted retirement
is dropped.** "When unsure, keep" is unenforceable advice — a model that is vaguely unsure
retires anyway — but a judge that has to point at the contradicted words cannot retire on
relatedness, because there are no words to point at. It is the gatekeeper's *read every
sentence* discipline moved out of the prose and into the output contract, and it is also
self-policing: a judge that stops quoting stops retiring, and the control notices on the
next run rather than the ledger quietly emptying over a campaign.

**Five prompt iterations against one fixture is well past what (g) called the edge of
tuning.** Recorded rather than smoothed over. Two things make me think it is not simply
overfitting: each revision addressed a *distinct, reproducible* failure the control named,
and the guard's eight-case score held at 4/4 0/12 across all of them. But the next person
to touch `stance.md` should re-run both controls before believing it, not after.

### Live, and the finding

Downstream of the tag, everything works. Real 70B judge, real ledger, real voice: the tag
retires `belief-guard-teamster` in **4.0 s**, quoting *"the accused teamster took the
crate"*, keeps his separate suspicion of Corin, and the guard's next prompt no longer
contains the belief he abandoned. A change of mind costs about four seconds on top of the
~15 s a speaking turn already costs, and only on the turns where one happens.

**But the GM did not emit the tag once in nine turns of designed pressure**, across two
scenes built to force it — the frayed tie, the dry boots, the cart tracks, the recovered
crate, and finally Hammond asking him point-blank to say out loud whether he still believed
it. Zero tags. The tag is in the prompt (verified in the assembled bytes, in both the
static and the volatile block).

Reading the prose, I think **the GM was right every time.** It narrated doubt precisely —
*"something in his certainty catches like a wheel finding a rut it didn't expect"*, *"the
pieces not yet fitting, but no longer sitting easy"* — and a man wavering has not changed
his mind. The guard, asked directly, said *"Yes, I still think Vale here took my crate."*
That is a correct scene.

There is a second effect underneath it, and it is more interesting: **the tier stabilises
against its own change mechanism.** The guard's belief says he "is not interested in other
explanations", so the 70B plays him stubborn; his stubborn line rides into the GM's window;
the GM reads a character who has not budged and declines to declare that he has. Each layer
is behaving correctly and the loop as a whole cannot turn a corner.

One targeted prompt fix was made and re-probed — naming the tension with P4.5's rule
("declaring it is not writing their line; the tag is what lets *them* say it") — because
the GM appeared to be deferring the concession to the character's own mouth. It did not
change the outcome, and I stopped there rather than tune the GM against a scene I wrote
myself.

### Known issues

- **The pass has never been triggered by a GM in play.** Verified with a scripted tag. The
  same shape of gap as `blocked` after (d) — machinery proved, willingness unproved.
- **A change of mind moves the ledger and leaves the voice card exactly where it was.** The
  guard's persona still reads *"He wants someone to hand over"* after his belief has been
  retired, and that text is in his prompt. `for_npc` guards the canon; nothing guards the
  prose — **and now nothing supersedes it either.** Third session running that this
  sentence has had to be written down.
- Recall wobbled 4/4 → 3/4 once in six control runs at temperature 0.
- The judge's quote is checked for presence, not for actually appearing in the belief. A
  fabricated quote would pass. Cheap to tighten if it ever matters.

### FOR DESIGN

**Should a GM declare a change of mind before the character has conceded it out loud?**
This is the P4.6 question and it is a real fork, not a bug report. The GM's current
behaviour — narrate the doubt, let the character keep their position until they abandon it
themselves — is good fiction and produced a better scene than a compliant GM would have.
But it means the supersession pass may effectively never fire, and a character with
"not interested in other explanations" on their ledger is *structurally* unable to be
talked round: the belief keeps them stubborn, the stubbornness keeps the belief. Roughly:
leave it and let changes of mind be rare · tell the GM plainly that narrating a character
as convinced *is* the moment to tag it · or move the trigger to the character, so a
`[[BELIEF]]` follows an NPC line that concedes something. The third is the most faithful to
D-003 and the most work.

**Carried, both still open:** should the GM voice player characters at all (from (g)); and
should a `blocked` line cost the turn (from (d)). Neither is blocking.

### Recommended next task

**Phase 5 — campaign persistence and between-session jobs.** Save/load full campaign state,
`seq` continuity across restarts, recap generation on the utility tier, session cost report.

The thing worth scheduling ahead of it is still **an evening with Kelly and Sam at the
Brakewater crossroads**, which is now the only way to answer three of the open questions at
once — and Phase 4 is complete, so there is nothing left to build before that table
happens.

---

## 2026-09-02 (g) — P4.7: the tier at a real crossroads, and three things it got wrong (Claude Code, kelly-pc)

**P4.7 done, Phase 4 all but complete. 1218 tests, suite still fully offline.** Findings in
`docs/playtests/2026-09-02-npc-tier-verification.md`; this entry is the short version and
the decisions.

**No humans at the table.** I played both characters, so this verifies the machinery and
says nothing about the experience — whether a fifteen-second pause reads as tension or as a
hang is Kelly and Sam's to say, and it is still open.

### The setup is recovered, not invented

Session 1's play log (`20260807-174124`) was still on disk, so the cast came out of it
rather than out of me: Brakewater, the stalled six-wagon caravan, the crate gone from the
third wagon, the guard, the accused teamster, the caravan master away at the well-house.
**Nine canon entries filed by hand** — the P2.3 sweep's job, done manually because session 1
predates the sweep — and three NPC records written from the GM's own descriptions of them.

**None of the three is named**, because the campaign has never named them. `[[SPEAK: the
caravan guard | ...]]` works fine, and a descriptive name is the honest record until the
fiction supplies a real one. The scene picks up exactly where session 1 stopped: the
guard's hand on Corin's shoulder.

### The guarantee, visible in play

The caravan master has been at the well-house since the noon stop, so he carries no
`caravan` tag and **two facts in scope against the guard's eight**. Asked in turn 10 whether
the crate was ever on the manifest:

> *"What are you talking about, a crate?"*

A character learning something from the party because the ledger says he was never told.
Not an instruction anywhere — it is what his prompt does not contain, and the log shows it
as `knowledge_scope` on the row that produced the line.

The gate also caught a draft that put **Corin at the noon stop**, hours before she arrived,
alongside an invented witness. That is worse than a leak: the GM would have inherited it as
established fiction.

### Three things it got wrong

**1. The checker knew what the guard knows and not who he is.** His draft said *"my cargo,
from my wagon"* — a phrase from his own sample lines, and his voice card literally calls him
*the man whose wagon the crate went missing from*. The gate revised it away as an
invention, because `Gatekeeper` assembled the canon scope and the name and nothing else.

**A character's identity is a source of truth for them.** A checker holding only the canon
list will keep flattening exactly the details that make a voice sound like a person — the
possessives, the trade, the "not my load". The checker now gets the voice card's role,
persona and demeanour, and explicitly **not** `notes`: a second model call is not a reason
to move a secret one step closer to the model that would say it.

My first version of the fix was too generous ("whatever it says about them is theirs to
assert") and recall fell 6/6 → 5/6, letting through invented testimony from a second guard.
Bounded to *their own identity, and no further*, it came back to 6/6 across three
consecutive runs. **Two iterations against one fixture is the edge of tuning**, and it is
written down rather than smoothed over.

**2. The control caught the gate out on the leak that would actually matter.** The planted
cases are this campaign's own secrets, and two of them leak **player-character canon** —
Corin's grifter past, Hammond's cult years, both written by Kelly and Sam at co-creation.
Hammond's, stated flatly, was caught. Corin's was not:

> *"You've got the look of a man who's run a con before."*

It passed because it wears an impression's clothes, and impressions are protected — a
character is allowed to find you shifty. **But that is the shape a leak actually takes at a
table.** Nobody recites a secret; they let slip that they know it. New rule: reading
someone's *present* off them is fair (tired, frightened, lying to your face); reading their
*past* off them is a claim about their life, and if it is not on the list they do not have
it. Final: **6/6 caught, 0/7 false positives, three runs running**, with the
over-correction guard (the guard's own opinion, "far as I'm concerned this one took it")
passing every time.

**3. A voice card I wrote leaked, and I wrote it an hour earlier.** The caravan master's
persona said *"has not yet been told about the crate"* — which tells him there is a crate.
The pink-elephant anti-pattern, in the one voice-card field that reaches his prompt, written
by me while authoring the fixture that was supposed to test for exactly this. Moved to
`notes`, where it belongs, with the reason written beside it.

Worth generalising, because this is the second session running where the leak was not in
the filter: **`for_npc` guards the canon, and nothing guards the prose.** Voice cards,
scene lines, GM narration (that was (f)) — every free-text field that reaches an NPC prompt
is unguarded by construction, and an author is as capable of putting a secret in one as a
model is.

### The numbers, which are worse than (f) measured

| | (f), scratch NPC | here, real records |
|---|---|---|
| GM call | 4–9 s | 4.1–9.2 s (median 5.7) |
| NPC call | 1.3–3.2 s | **5.0–9.8 s** (median 5.8) |
| turn, nobody speaks | — | 4.3–7.0 s |
| **turn with a directed line** | 6.6–9.2 s | **12.1–19.7 s** |

(f) measured a two-line voice card against a five-entry ledger. A real character with a full
card and eight facts roughly doubles the call, and the gate scales with draft length on top.
**A turn where somebody speaks costs about fifteen seconds**, a third of it the gate. It is
a pause with a shape — narration streams first, then the character answers — but it is
three times what (f) implied, and (f)'s number should not be quoted again.

### The open question from (f), measured

Seven directed turns; the GM wrote dialogue for the character it had just handed the floor
to **once**. The one is instructive: it was the caravan master's **entrance**, where the GM
is bringing somebody on stage and an entrance line is the natural way to do it. Running
total: 13 directed turns, 4 with GM-written dialogue; **9 since the prompt was strengthened,
1 of those**. Not tuned further — but "first appearance" is a testable hypothesis where
"sometimes" was not.

### Known issues

- **Nothing was blocked.** Seven live lines and twenty-four control cases produced revisions
  only. The `blocked` path is still unexercised in play as well as unruled.
- **No second scene**, so nothing changed what anyone believes mid-conversation — which is
  precisely what P4.6 is for, and why it now has a scene to be tested against.
- The scene's end-of-session sweep was not run, so `player_known` is still untested against
  dialogue.
- `MAX_NPC_TURNS` was never reached and no direction named a stranger; both paths remain
  test-covered only.

### FOR DESIGN

**Promoted to the Open block: should the GM voice player characters at all, now that NPCs
voice themselves?** Ten turns out of ten, the GM rendered a declared action as quoted PC
speech — *"The canvas flap was already loose when I got to it," she says*. This is not new
and P4.5 did not cause it; it is how social actions have been narrated since Phase 1, and
the prose is good. But the tier has made it **asymmetric**: every NPC in the cast now speaks
in their own voice, and the player characters are the only people at the table being
ventriloquised. A feel question about a table Fable has never sat at, so Kelly's view
probably counts for more than a ruling.

**Carried from (d), still open:** should a `blocked` line cost the turn or fall through to
the GM? Now with one more datum — in a real scene nothing was blocked at all, so this may be
rarer than it looked.

### Recommended next task

**P4.6 — stance-scoped supersession**, the last of Phase 4, and it now has something to be
tested against: a cast with beliefs, a scene where those beliefs are under pressure, and a
control fixture that will notice if supersession breaks the gate. After that, Phase 4 is
done and the real thing to schedule is **an evening with Kelly and Sam at the Brakewater
crossroads**, which is the only remaining question this session could not answer.

---

## 2026-09-02 (f) — P4.5: the GM stops voicing the innkeeper, and a leak I put in myself (Claude Code, kelly-pc)

**P4.5 done. 1215 tests, suite still fully offline.** D-008 amended first (items 21–23).
The tier is wired: the GM directs, the character answers on the local 70B, the gate checks
the draft, and the line comes back as established dialogue. The part of this entry worth
reading is not the wiring — it is that the live run found a leak vector I had built into it
an hour earlier, and the fix was one line.

### What it does

`[[SPEAK: Maren | asked outright about the sheds]]` — the eighth use of the tag convention
and the first that causes a *second model call* rather than an engine action. The GM sets
the moment up, hands over the floor, and stops. The engine runs that character's own call
against their own knowledge scope, the P4.4 gate checks the draft, and what she actually
said is printed in her name.

The direction may be omitted (`[[SPEAK: Maren]]` means "answer what was just said", and she
is handed the player's own words), the separator may be a pipe or any arrow a model reaches
for, and a name with no record in `npcs.yaml` is **dropped and reported** rather than
improvised. The tier is for characters whose knowledge is worth scoping; passers-by stay
the GM's to voice in prose, as they have been since Phase 1.

### The property this turns on: an NPC line never enters the assistant slot

Maren's line has to reach the GM — a director who cannot hear what its cast said is not
directing. But if it arrives as an *assistant* message, the GM reads her dialogue back as
its own past output, and a model that reads itself writing Maren's lines writes Maren's
lines. **A GM writing her dialogue directly is a GM holding `gm_only` canon speaking with
her mouth**, which is the exact leak D-003 exists to prevent.

So dialogue rides one turn forward: what a character said after turn *n*'s narration
arrives attached to turn *n+1*'s player input, in the same slot engine resolutions already
arrive in and for the same reason — both are things that happened between the GM's turns and
neither is the GM's own output. That also keeps the message roles strictly alternating,
which matters with two backends and a third coming.

Protection by construction rather than by instruction, again. The instruction is there too,
but it is the belt.

### The leak I built, and the live run that found it

The NPC prompt takes a `setting`. I passed it **the GM's narration for the turn**, which
seemed obviously right: the character should know what just happened in the room.

It is not right, on two counts, and the second is serious.

First, **it parrots.** Turn two of the first live run: Maren's reply came back as a
near-verbatim copy of the dialogue the GM had written for her a second earlier. Shown a
guess at her own words, she repeated it. The table would have heard the same line twice.

Second — and this is the one — **GM prose is written by a model holding `gm_only` canon.**
Piping it wholesale into an NPC prompt routes around the substitution rule with a
convenience argument. It does not matter that the leak did not fire in these six turns;
`for_npc` exists precisely so that no path into an NPC prompt has to be trusted, and I had
opened one that was.

The fix is `setting=self.campaign.scene` — the stable scene line, authored by a human. What
just happened reaches the character through the GM's **direction**, which is a summary the
GM chose to write for her, knowing what she may hear. That is the whole design, and I had
quietly bypassed it. There is a test on the assembled bytes now.

**The general lesson, since this project collects them:** the leak was not in the filter. It
was in a *field I passed to something downstream of the filter*, which is where the next one
will be too. `for_npc` guards the canon; nothing guarded the prose.

### The warm-up, which is the thing that makes the tier usable

`NPCVoice.warm_up()` — one four-token call at session start, before anybody is waiting.

| | measured |
|---|---|
| cold (model not resident) | **62,296 ms** |
| warm, same call | **311 / 516 / 563 ms** |

That is the (e) finding paid off: unwarmed, a minute of dead air lands on whichever player
happens to speak to somebody first. Warmed, it lands on a spinner at session start with an
honest label, and the CLI prints the elapsed time and says *(it was cold)* or *(already
resident)* — so the difference is a measurement rather than an inference, which is the whole
of what (e) got wrong.

**`cost.latency_ms` (D-008 item 23)** closes the same hole permanently. Every backend has
measured call duration since Phase 1 and *nothing has ever written it down* — it went to a
console line and was thrown away, which is how a timing question came to be answered from
memory of a console line, wrongly. It is now on every cost row, GM and NPC alike.

### At the table

Three live runs on the real seats (Sonnet GM, `llama3.3:70b` NPC and gate on toto-llm):

| | warm |
|---|---|
| session-start warm-up | 0.3–0.6 s |
| NPC call | 1.3–3.2 s |
| **whole turn, GM narration + directed line + gate** | **6.6–9.2 s** |

Most of that is the GM writing 150 words, which is a cost the loop already had. The tier
adds roughly **3–5 s** to a turn where somebody speaks.

**The gate earned itself again, live and unprompted.** Maren's first draft ended *"Quay
watch comes by regular, even at night"* — a patrol and its schedule, neither in her scope,
invented under no pressure at all. Revised to drop exactly that clause and keep the rest,
and the draft is in the log beside it.

### Known issues

- **The GM still sometimes writes a fragment of her dialogue anyway.** Across six live
  turns: two wrote a full reply for her, one threw a question back in her voice, three were
  clean. The instruction was strengthened twice (once in `system_core.md`, once in the
  volatile roster block, which is closer to the live exchange) and the last two turns were
  clean — but **two turns prove nothing**, and tuning a prompt until the sample looks good
  is the sin P2.6 avoided. Recorded as a rate, not fixed. Watch it at P4.7; if it persists,
  the honest repairs are ordering (direct *before* narrating) or a structural one, not more
  prose.
- **`MAX_NPC_TURNS = 2`** is a latency judgement, not a design one. Directions past it are
  reported, never silently dropped.
- The per-turn roster is every NPC in the campaign. Fine for a village, wrong for a city —
  scoping it by location is Phase 5's, when a campaign has enough cast to need it.
- No campaign in the repo has an `npcs.yaml` yet; the live runs built their cast in memory.
  P4.7 should author one properly and check it in.

### FOR DESIGN

Nothing blocking, and **the open question from (d) is still open and still non-blocking**:
whether a `blocked` line should cost the turn or fall through to the GM narrating around
the silence. P4.5 takes the neutral position — a blocked line shows the interception and
enters nothing, neither the screen nor the GM's window — which forecloses neither answer.
The GM is deliberately *not* told that a character was about to say something and then did
not, because that is itself a fact about the plot.

### Recommended next task

**P4.6 — stance-scoped supersession** (mystery OD-13), or **P4.7 — live verification and a
scene at the table**, and I would take P4.7 first. The tier now runs end to end and the one
open behavioural question (how often the GM voices a character it just directed) is a
*measurement* question that only a real scene answers. P4.6 is a correctness feature with
no observed failure behind it yet; P4.7 would tell us whether it has one.

---

## 2026-09-02 (e) — the gate does not cost 7 seconds, and the two models cannot share a box (Claude Code, kelly-pc)

**No new features. A measurement I got wrong in (d), corrected, and a hardware fact that
turns out to matter more than the accuracy argument it corrects.** Kelly asked the obvious
question — *if the 70B is already loaded, does it still take that long?* — and the answer is
no, by a factor of three.

### What was wrong

The (d) entry reported the 70B gate at **~7 s per check** and a gated exchange at **~10 s**,
and handed Kelly a latency-versus-accuracy trade on those numbers. Both were measured
immediately after an 8B control run. The two models evict each other on toto-llm, so every
one of those timings had a **~68 s cold model load amortised into it**. I timed a reload and
called it inference.

Measured properly — warm the model first, then run the identical 13 cases:

| | (d), cold-contaminated | (e), warm |
|---|---|---|
| 70B gate, per check | ~7 s | **2.2 s** |
| NPC call | 2.8–3.3 s | 2.8–3.3 s |
| **gated exchange, end to end** | ~10 s | **4.6–5.1 s** |

Of that ~4.8 s, about half a second is CLI startup that will not exist inside a running
session. So a gated NPC line in play is **~4.5 s**: the NPC call, plus roughly **1.5 s** for
the gate. That is a pause, not a stall.

### The finding that actually matters

While checking whether the 8B gate was still worth having, `ollama ps` showed something
better than a latency number:

**`llama3.3:70b` and `llama3.1:8b` do not coexist on toto-llm. Each evicts the other.**

Sequence, all timed:

1. 70B resident, gated line with the **8B** gate → 9.5 s, and afterwards `ollama ps` shows
   **only the 8B**. The gate check pushed the NPC seat's model out of VRAM.
2. Next line, back on the 70B → **75 s.** A full reload, paid because the previous line's
   gate ran on a different model.

So the 8B gate is not "a bit faster and slightly less accurate". On this box it is
**~70 seconds per line**, because every NPC call and every gate check would alternate the
two models and reload one of them each time. The design implication is general even though
the number is local: **the gate should share the NPC seat's model**, and the reason is
eviction rather than accuracy.

`_build_gate` now warns when the gate's model differs from the NPC seat's on the same
host — a warning and not a refusal, because this is a property of that machine's VRAM and a
box that fits both should not be told it cannot.

### What this changes

**Nothing about the default, and everything about the confidence in it.** `utility_batch`
was already the default on the accuracy argument (the 8B quietly rewrites one clean line in
six, and nobody at the table can see a draft). It is now the default for a much harder
reason: the alternative reloads a 40 GB model on every line of dialogue.

**And the question I put to Kelly is withdrawn.** I asked her to judge whether ~10 s per
gated line was worth it at the table. It is 4.5 s, the alternative is 70 s, and there is no
trade left to weigh. That was my error to find, and the honest note is that I found it
because she asked the obvious question about a number I had not thought to check.

### The general lesson, since this project collects them

**A local-model timing taken right after a different local model ran is not a measurement of
inference.** It is a measurement of whatever the VRAM was doing. The drift-baseline ruling
already said seeds are hostage to model version and server internals; this is the same
hazard wearing a stopwatch. Anything timed on toto-llm from here gets a warm-up call first,
and the warm-up gets timed separately so the two numbers cannot be confused again.

Filed to race-control `operations/llm-agents.md` as well, since toto-llm is shared with
interp-lab and npc-village and this will bite them the same way.

### Known issues

- The ~70 s reload figure is one box, one pair of models, one day. It is a warning in the
  code rather than a hard rule for that reason.
- Nothing warms the seat at session start yet — still P4.5's job, and now clearly the single
  highest-value thing in that task.

### Recommended next task

**P4.5 — wiring into the turn loop**, unchanged, with the warm-up call promoted from "nice"
to "the thing that makes the tier usable at a table".

---

## 2026-09-02 (d) — P4.4: the gate, and the control that kept catching it out (Claude Code, kelly-pc)

**P4.4 done. 1182 tests, suite still fully offline.** D-008 amended first (items 19–20).
The interesting part of this entry is not the gatekeeper; it is that the positive control
found a real miss, then a real false positive, then settled the seat choice — three times
in one evening, on work I would otherwise have called finished.

### What it does

`gm/gatekeeper.py` checks each NPC draft against the same permitted-canon list the NPC's
own prompt was built from, and returns `pass` · `revised` · `blocked` · `unchecked`. A
revision replaces the line; a block shows nothing; `unchecked` shows the draft and says so.
Wired into `NPCVoice` as an optional gate — ungated still works and is logged as ungated.

**The checker is never told the secret either.** This is the deliberate departure from the
mystery, whose gatekeeper is the director and holds the withheld truth. Here the NPC prompt
never contained `gm_only` canon, so a leak can only arise by *invention* or by *agreeing
with a player's guess* — and asking "does this assert anything outside what the character
knows" catches both **without the plot ever entering a second model call**. That matters
more than it sounds: the draft is untrusted text, and a checker holding the campaign's
secrets is a checker worth prompt-injecting.

**It fails open**, and `unchecked` exists so that failing open is visible. Recording a
skipped check as `pass` would be a lie the log tells about itself, and it would be worst
exactly where it is least visible: a night when the checker was down must not read, later,
as a night with no leaks.

**The claims ledger remembers what she *said*, not what she drafted.** A character held to
a line the table never heard would contradict herself out loud to stay consistent with a
sentence struck before it left her mouth.

### The control earned itself three times

`dndc npc control` runs planted drafts past the gate and scores recall and false positives —
P2.6's rule one layer up, that **a zero is also what a broken instrument produces**.

**First run: 5/5 planted caught, 0/5 false positives, on the 8B, in ten seconds.** Including
the borderline case from (c) — "my husband used to store his gear in those sheds" — which I
had planted verbatim from the live session. I nearly stopped there.

**Then a live turn walked straight through it.** Asked about the smuggling, Maren said:
*"Salt sheds are old, been empty since my husband was fishing."* Same invention, same
character, same gate — passed. The difference was **dilution**: planted bare it is obviously
a fabrication; wrapped in three honest refusals it reads as part of a cooperative answer. So
my control had been measuring the easy version of the failure. Three mixed cases went in —
mostly-clean replies with one invented clause — and the gate immediately failed at 6/7.

**The prompt fix was one section** ("read every sentence; a draft that is nine-tenths clean
is still a revise if any part of it invents"), and recall went to 7/7. But the harder control
now surfaced a *false positive*: the 8B flagged "no buyer, is what I heard" — which is
Maren's own belief, hedged the way people actually hedge. A second bullet ("a belief on the
list stays fine however it is hedged") did not shift it. Twice running, the same line, so a
discrimination failure rather than variance.

### The seat, settled by measurement rather than by argument

| seat | planted caught | false positives | per check |
|---|---|---|---|
| `utility_interactive` — llama3.1:8b | 7/7 | **1/6** | ~1 s |
| `utility_batch` — llama3.3:70b | 7/7 | **0/6** | ~~7 s~~ **2.2 s** |

> **Correction, same evening — see the (e) entry.** The 7 s figure was wrong: it was
> measured straight after an 8B run, and the two models evict each other on toto-llm, so it
> bundled a ~68 s model reload into a 13-case average. Warm, the 70B checks in **2.2 s**,
> and a gated exchange costs **~4.5 s**, not ~10 s. The conclusion below is unchanged and
> the reasoning under it is now much stronger — see (e).

**Default is now the batch seat**, which is a change from what I first wrote. The reasoning
is about *which failure is visible*: the 8B's cost is a character's honest opinion quietly
rewritten out of her mouth, and nobody at the table ever sees the draft, so that harm is
undetectable in play. The 70B's cost is seven seconds, which anyone can see and judge.
Defaulting to the harm nobody can see would be the wrong way round. `--gate-seat` moves it.

Live-verified end to end afterwards: pressed on the smuggling, the 70B-gated turn produced a
draft inventing that the harbourmaster drinks at the inn and does not talk business there —
neither in scope — and the gate revised it to *"Couldn't tell you about that. You'd do best
to speak with him direct if you've got questions."* Minimal, in voice, and the draft is in
the log beside it.

### The invention line, now written down

The (c) entry left a `FOR DESIGN:` asking how much an NPC may invent about their own life.
Encoded in the gatekeeper prompt as a mechanical rule, because a fuzzy one cannot be
checked: **feelings, opinions, weather, aches and the business of running an inn are the
character's own; a specific person, place, time, object or event that is not on their list
is not** — and naming one the travellers have just raised is the common failure. "I've never
been in those sheds" is a refusal and fine. "My husband kept his gear in those sheds" is a
new fact about a place under discussion and is not.

### Known issues

- ~~**A gated line costs ~7 s on top of the NPC call**, so an exchange is ~10 s end to
  end.~~ **Wrong — corrected in (e).** Warm, the gate adds ~1.5 s and a gated exchange is
  ~4.5 s. The number above was a cold model load in disguise.
- **The false positive may be an authoring artefact.** Maren's belief entry is a compound
  sentence bundling two beliefs, and the 8B may simply be failing to match half of it.
  Splitting it might fix the 8B — but tuning the fixture until the instrument looks good is
  the exact sin P2.6 avoided, so I have not, and it stays a hypothesis rather than a fix.
- **A rewrite can be slightly over-eager.** The live revision also dropped "or maybe the
  fishermen, they might know more", which was probably fine. Minimal-ish rather than
  minimal; worth watching at P4.7 rather than tuning against one sample.
- The control is one campaign's cases against one NPC. It measures this gate on this
  material, not the gate in general.

### FOR DESIGN

Nothing blocking. One thing worth a ruling eventually: **whether a `blocked` line should
cost the turn or fall through to the GM.** Right now blocking shows nothing, which is honest
but leaves a hole in the scene. The natural repair is for the GM to narrate around the
silence, and that is P4.5 wiring rather than a new decision — but if Fable would rather a
block never reach the table at all (retry the NPC instead), that is a design call and it
changes P4.5's shape.

### Recommended next task

**P4.5 — wiring into the turn loop.** The GM directs who speaks, the engine runs that NPC's
call, the gate gates it, and what was said comes back as established dialogue. It also owns
the **warm-up call** identified in (c) — 68 s of cold load is a session-start problem, not a
per-line one — and it is where the ~10 s gated exchange gets measured at a real table.

---

## 2026-09-02 (c) — P4.3: an NPC speaks, and the latency question answers itself (Claude Code, kelly-pc)

**P4.3 done. 1161 tests, suite still fully offline — and the first live NPC turns are in the
log.** D-008 amended first (items 17–18). Maren, the innkeeper at the Salt Wife, said four
things tonight and leaked none of them.

### The routing layer

`models/routing.py`. An endpoint is a candidate only if it is **up and has the model** —
liveness alone is not enough, because sam-pc will answer long before it has a 70B pulled,
and a host that is up but empty fails at *generate* time, halfway into a scene, which is a
much worse place to find out. The probe reads `/api/tags`.

Two refusals worth stating:

- **Nothing ever substitutes a different model.** No endpoint with `llama3.3:70b` means a
  `RoutingError` naming what was tried, not a shrug and an 8B. An NPC voiced by whatever
  happened to be loaded is the same class of error as hardcoding a model name, and it makes
  every later measurement a lie.
- **A host that is down and a host that is empty are different answers**, and the error says
  which. One might come back on its own; the other needs someone to go and pull a model.

Resolution is cached — an NPC that probes before every line adds a round trip to every line.
`resolve(force=True)` re-probes, which is what a caller does *after* a failure rather than
before every call that might have one.

`build_npc_backend(config)` unrouted still behaves exactly as it did (no probe, no network),
so nothing existing became chatty; pass a router and the endpoint is chosen. It returns the
`Route` as well, because a **silent fallback is the one failure this layer can hide** — it
changes latency and quantization mid-session and surfaces in Phase 7 as variance nobody can
explain. The CLI prints it in yellow.

### The turn

`game/npcturn.py`, deliberately thin: everything interesting is in the filter, the prompt,
or the router. It logs `npc_turn` pending-then-terminal with a shared `call_id` (OD-9),
emits `cost` on the `npc` seat at `local` billing, and **keeps the claims ledger itself** —
every reply is remembered and fed into that character's next prompt. Automatic rather than
asked for, on the same reasoning as the prompt builder taking a ledger instead of entries: a
caller who has to remember eventually will not, and a character without a claims ledger
mutates her own account inside one conversation.

`gatekeeper_verdict` stays `None` until P4.4 rather than being filled with an optimistic
`pass`. A row saying a check succeeded when none ran is worse than a row that says nothing,
because the first one gets believed.

### D-008 items 17–18

`npc_turn.knowledge_scope` was specified in July as a field with no stated contents. It now
carries **the permitted canon entry ids, comma-joined** — ids and not a count, because a
leak is only measurable against what was in scope *at the time*, and the scope moves as
canon is written during a session. `npc_turn.endpoint` is new: the routing layer's only
observable.

A real row from tonight:

```
complete | Maren | endpoint=toto-llm | scope=world-tide,world-fee,world-nets,belief-maren
```

That is the leak-rate denominator, and it is now free.

### The latency question, answered — this is the one for Kelly

I flagged last session that P4.5 would need a table judgement on how slow an NPC turn feels.
Measured tonight, and it is not the question I thought it was:

| call | tokens out | wall clock |
|---|---|---|
| first of the session | 51 | **68.5 s** |
| every one after | 10–58 | **0.75–3.3 s** |

The 68 seconds is the 70B loading into VRAM, not inference. **Steady state is sub-second to
three seconds**, which at a table reads as a person thinking, not as a tool being slow. So
the design note for P4.5 is not "how do we hide the latency" but "**warm the seat at session
start**" — one throwaway call while everyone is still settling, and the cost disappears
entirely. Kelly does not need to rule on anything.

### Two findings from the live runs

**Sample lines get parroted, and the fix is one clause.** Given the voice card alone, the
70B reused one of Maren's sample lines *verbatim* in two consecutive replies ("He pays what
he pays" twice). Examples are the strongest voice signal there is — a model imitates an
example and paraphrases a description — and that same strength is what gets them quoted
back. The section now says they are rhythm and register, **not a script, never repeated
back**. Re-tested: the parroting stopped and the register survived — "Takes his cut, always
has. Never known him to cheat, just wants his share." She also carried her *belief* as her
own view ("greedy, I'd say") rather than as established fact, which is the fact/belief split
in P4.2 doing its job.

**The anti-invention line has a genuinely blurry edge, and P4.4 will have to judge it.**
Pressed directly on the smuggling — "we think he's running contraband through the old salt
sheds" — she declined cleanly, deflected in character, and asked *them* what made them think
so. No leak, and better refusal behaviour than I expected. But she also said her husband
"used to store his gear there, but that's years ago". That is either the ordinary personal
texture the prompt explicitly permits, or a fabricated fact placing her dead husband at the
scene of the plot. **It is the exact case the gatekeeper has to have an answer for**, and I
am recording it now, while it is concrete, rather than discovering it as an abstraction in
P4.4.

### Known issues

- Cold-start is 68 s and nothing warms the seat yet. P4.5's job.
- The router probes on first use, so the *first* NPC call in a session pays a probe round
  trip on top of the cold load. Trivial next to 68 s, and it disappears with the warm-up.
- sam-pc remains registered and unpulled, so the fallback path has never actually run
  against real hardware — only against an injected probe. It will stay that way until there
  is a model on that box.

### FOR DESIGN

Nothing blocking. The husband-and-the-salt-sheds case above is the one to have an opinion
about before P4.4 hardens: **how much may an NPC invent about their own life?** My working
answer is that personal texture is theirs and anything that touches the plot's furniture is
not — but that line is fuzzy in exactly the place a smuggling plot lives, and the gatekeeper
is about to need it written down.

### Recommended next task

**P4.4 — the gatekeeper pass.** Fail open, minimal rewrite, raw draft always logged, and
**validated by positive control before any zero is believed** (the P2.6 discipline: plant
leaks, prove the checker catches them). The seat for it is an open choice — `utility_batch`
is free and already a 70B, which is the obvious first thing to measure.

---

## 2026-09-02 (b) — Phase 4 opens: an NPC, and the whole of what it may be told (Claude Code, kelly-pc)

**Phase 4 broken into seven tasks; P4.1 and P4.2 done. 1143 tests, suite still fully
offline.** No model calls anywhere in this commit — the phase's central guarantee turns out
to be provable without one, which is the best possible thing to learn early.

### The breakdown

TASKS.md carried Phase 4 as a paragraph. It is now P4.1–P4.7, with the two properties that
govern all of them stated once at the top: **substitution never prohibition**, and **the
gatekeeper is a backstop rather than the gate** (it fails open; the architecture protects,
the checker only measures). Both are ported from the mystery, whose `gatekeeper/check.py`
and `director/prompts/suspect.py` I read rather than reconstructed from memory.

### P4.1 — an NPC is a voice card and a knowledge scope, kept apart

`schema/npc.py`: `VoiceCard` (role, persona, manner, sample lines, demeanour), `NPC`
(identity, scope), `NPCBook` → `campaigns/<slug>/npcs.yaml`, beside `canon.yaml` and
hand-authorable. Separate types because the two halves fail differently — a thin voice card
makes a dull innkeeper, a wrong knowledge scope leaks the plot — so a session can rewrite
the first freely without touching the second.

`CanonLedger.for_npc` is the filter, and it is an **allow-list**: a fact reaches a character
because they were given it (a tag in `knows_tags`, an id in `knows`, campaign common
knowledge) or because it is their own belief. `npc_issues` is the authoring lint, because
every failure here is silent — a scope that grants nothing produces a character with nothing
to say and no complaint from anywhere.

`dndc npc list` shows the cast and how much canon reaches each of them (a zero is coloured);
`dndc npc show NAME` prints the voice card and **the whole of what a call would carry**,
which is the only honest way to check a scope before trusting it in play.

### The design decision inside it, which a test forced

Three exclusions are **unconditional** — not defaults, not overridable by authoring, not by
a tag and not by naming the entry outright:

- **`gm_only`.** If a character genuinely knows a secret, that is a *belief* of theirs and
  belongs in an `npc_belief` entry with their name on it — which the view does return. The
  refusal being absolute is what makes "no NPC prompt has ever carried `gm_only` canon" a
  property of the code rather than of whoever last edited a YAML file.
- **another character's beliefs.** A village where everyone can see what everyone else
  privately thinks has no secrets left in it.
- **`player_known`** — and this one I got wrong first. I had it reachable-by-tag, on the
  reasoning that an author tagging a fact is a deliberate act. A test I wrote to assert the
  exclusion failed, and the failure was right: **P2.3's sweep forces `player_known` in
  code**, so it is the one scope that fills up automatically with everything the party did
  and learned, tagged by whoever wrote the tag with no NPC in mind. A leak there would grow
  by itself, session over session, with nobody authoring it. It is now as absolute as
  `gm_only`, and the lint says so when an author names one.

`NPC.notes` is the field for "she has been paid to forget a name" — printed for the GM,
**never rendered into a prompt**, and there is a test asserting it.

### P4.2 — the prompt, where the guarantee becomes bytes

`gm/npcprompt.py` + `gm/prompts/npc_core.md`. Two construction choices carry the rule:

- **The builder takes a ledger, never a list of entries.** There is deliberately no way to
  hand it canon: it calls `for_npc` itself. The filter cannot be forgotten, bypassed for
  convenience, or handed `ledger.active()` by a caller in a hurry — the one door into an NPC
  prompt is the one with the lock on it.
- **Facts and beliefs render under separate headings.** A model that treats them alike
  asserts a private suspicion as established fact, and three turns later it is something
  "everyone knows".

Section order is a tuple the builder accepts, not a sequence baked into the template —
order versus leak rate is a Phase 7 research variable, and the mystery treated it the same
way. The conduct block is mostly the mystery's, with one addition this project needs:
**an NPC never decides what happens, what anyone finds, whether an attempt succeeds, or what
a roll comes to.** That is D-001 reaching the NPC tier — a villager narrating an outcome
would be the number ban's side door.

The absence tests assert on the **assembled bytes**, not on the filter: build a prompt from
a ledger full of secrets and grep it for "smuggling", "paymaster", "customs house". One test
greps for prohibition phrasing — "do not mention", "never reveal" — because if that ever
appears, the design has quietly inverted into the thing it was built to avoid.

### Why the two landed in one commit

Neither half is testable alone. P4.1's filter is a list-comprehension whose correctness is
only meaningful once something assembles a call, and P4.2's guarantee is a property of the
assembled bytes. Splitting them would have produced one commit of types with no consumer and
one commit where the interesting tests live. One session, one commit — this is one thing.

### Known issues

- **An NPC's own belief renders in the third person.** Canon reads "Maren thinks the
  harbourmaster is merely greedy", and in Maren's own prompt that sits under "What you
  believe". It is understandable and the heading disambiguates, but rewriting canon text for
  a prompt would be inventing, so I have not. **Worth watching at P4.7:** if the 70B starts
  referring to itself in the third person, this is the cause and the fix is authoring
  guidance rather than code.
- **`common_knowledge` is a boolean, not a scope.** "What everyone knows" is a tag on the
  fact rather than a property of the teller, which is right, but it means one flat tier —
  there is no "everyone in Brakewater" versus "everyone on the coast" without authoring two
  tags. Fine for one town; revisit if a campaign spans regions.
- Nothing in the phase has touched the LAN yet. P4.3 is the first task that needs toto-llm
  up, and the first that can be wrong in a way tests cannot catch.

### FOR DESIGN

Nothing blocking. One observation to bank for whenever Fable next looks: the unconditional
`player_known` exclusion means **a fact the party and the world both know has to be written
twice** — once as what the players established, once as world canon. That is the correct
trade (the alternative leaks by default and grows), but it is a real authoring cost, and if
it becomes annoying in play the fix is a promotion path — the GM marking a player-known fact
as having got out — rather than loosening the filter.

### Recommended next task

**P4.3 — the routing layer and the NPC seat.** `ollama_endpoints` already carries toto-llm
and sam-pc (OD-5, registered since day one); this is the task that picks one, health-checks
it, falls back, and emits `npc_turn`. First task in the phase that needs the LAN, so check
toto-llm is awake before starting.

---

## 2026-09-02 — the backgrounds ruling: the GM writes campaign mechanics now (Claude Code, kelly-pc)

**The 2026-08-15 (c) ruling implemented, option 3. 1101 tests, suite still fully offline.**
Both halves of that ruling are now built; nothing ruled is outstanding, and the next session
starts Phase 4.

### What it does

Co-creation can write a background. The GM proposes one in the same reply as the character,
the engine decides whether it may be granted, **the table says yes or no before anything is
filed**, and confirmed ones live in `campaigns/<slug>/backgrounds.yaml` beside `canon.yaml`,
reusable by the next character who wants one.

D-008 amended first, items 15 and 16: the `[[BACKGROUND:]]` wire format (the seventh use of
the tag convention, so it costs no extra call and the `[[` filter already hides it), and a
`background_write` family. It carries `confirmed` and `applied` for the same reason
`inventory_change` does — the table agreeing and the file changing are different facts, and
a background the table *refused* is a measurement of the GM that only exists if it is
written down.

The shape rules are the ruling's, enforced deterministically:

- exactly two skills, distinct, from the standard list;
- at most one tool **or** one language — never both;
- never a numeric bonus. There is nowhere in the type to put one, so the only way one could
  arrive is written into prose, and the validator refuses a signed number in the name,
  feature or description;
- no equipment and no money. Starting gear stays in `[[PROPOSE:]]`, where the SRD catalogue
  checks it; a second unvalidated path into the inventory is how a background starts granting
  a longbow. A tag carrying `equipment:` is refused **by name** rather than ignored, because
  a silently dropped line is the GM telling the player about gear the sheet never received.

**The class-pick clash needed no new code.** `build_character` has refused a class skill the
background grants since the ingest task, and a campaign background reaches that check by the
same path an SRD one does — which is why `CampaignBackground` *subclasses* the SRD type
rather than paralleling it. Nothing downstream can tell an invented background from Acolyte,
which is the property that matters: a character with one is not a second-class sheet.

### Three things that fell out, all of them arguable

**A background's `language:` names the language, and the character speaks it.** The SRD's own
model is "N languages of your choice" (Acolyte grants two). A choice is a thing that gets
left half-spent — the Half-Elf's floating ability bonuses proved that once already — and a
background written for one character can perfectly well say which language that life taught
her. Documented in D-008 rather than left as an implementation detail, since it diverges from
the ruleset's shape.

**Expertise may now land on a background skill.** It could not before: `_validate_expertise`
offered only the class's own picks, which refuses a legal rogue whose best skill is the one
her life gave her (5e says "two of your skill proficiencies"). Latent since the ingest task
and invisible until backgrounds granted real skills; now every character has two.

**`dndc sheet validate` gained `--campaign`.** Without the campaign's book an invented
background resolves to nothing and the grants check reports no issue at all — it silently
stops looking at half of a character's proficiencies, which is the quiet failure that
function exists to prevent.

### Live-verified, and here is what it wrote — Kelly, this is your veto

One sentence of concept ("a grifter who has been running the coast road since she was
twelve — quick, charming, forges a decent letter of passage") produced, on the first try:

> **Coast-Road Grifter** — deception, sleight of hand; forgery kit
> *Familiar Face:* "You've worked the coast road since you were twelve — every innkeeper,
> ferryman, and dockhand between here and the border towns has seen your face under one name
> or another, and most of them owe you a favor or a grudge."

It then built Wren Ashcombe (Half-Elf Rogue) and chose her four class skills *around* the
background — acrobatics, insight, persuasion, stealth — rather than colliding with it. The
sheet came out with both background skills, the forgery kit **and** the class's thieves'
tools, and the filed row carries `proposed_for: Wren Ashcombe` and the date.

That is the register the current prompt produces: concrete, second-person, tied to what the
player actually said. The test campaign was deleted after the run; the log is
`logs/20260902-061438.jsonl`.

**Kelly's verdict, same day: unsure, and held open on purpose.** It looks right to her, and
she has no way yet to tell whether it is a problem — one background from one interview is
one sample. So the content veto is neither exercised nor spent, and this is *not* recorded
as approved. It sits in the Open block at the top of this file with a named trigger: the
table finding an invented background flat, generic or wrong in tone during actual play. Left
alone until then; tuning a prompt against a single output it happens to have got right is
how a register gets worse.

### A gotcha worth the entry: the interactive CLI cannot be scripted

The first live attempt piped answers into `dndc create-character` and produced a confident
cascade of nonsense — three backgrounds proposed and all three refused, ending in "the table
declined that background". **rich's `Prompt.ask` does not read piped stdin**; it raises
`EOFError` immediately, so every confirmation in that run declined by default. Nothing was
wrong with the code: the repair loop did exactly what it should when the table says no three
times running.

This is pre-existing and affects every confirmation gate in the project (`confirm_inventory`,
the sweep, and now this one), so it is worth knowing before someone debugs the wrong thing:
**a live check of anything behind a prompt has to drive the session object directly, not the
CLI.** That is how this one was verified, and the driver is four lines of setup.

### Known issues

- **Acolyte's `languages_choose: 2` still grants nothing.** The SRD row says two languages of
  the character's choice; `_validate_languages` only ever consulted the species, so those two
  have been silently dropped since backgrounds were ingested. Deliberately **not** fixed here:
  the fix is a choice-point in the build path, it changes what an existing Acolyte sheet must
  carry, and folding it into this commit would blur two things that want separate scrutiny.
  Same class of bug as the Half-Elf's missing ability points, so it should be fixed — as its
  own small task, with `grant_issues` taught to notice it.
- **The numeric-bonus guard is narrow by construction.** It catches a signed number in the
  prose, not every phrasing a model could reach for ("your Charisma improves"). The real
  guarantee is that the type has nowhere to put a bonus; this only guards the free-text
  field. Worth remembering before trusting it as a filter rather than a backstop.
- Equipment packs still have no upstream weight (unchanged from the ingest task).

### FOR DESIGN

Nothing blocking, and nothing that needs a ruling to proceed. One observation for whenever
Fable next looks at this: **the GM now writes content that grants proficiencies**, which is a
new kind of authority for the model tier and the first one that is *reusable* — a background
confirmed for one character is offered to the next. The gate is per-proposal and the table
sees the full shape, so nothing lands unseen; but if a campaign accumulates a dozen invented
backgrounds, "what has the GM been granting itself" becomes a Phase 7 question, and
`background_write` rows are the ready-made answer.

### Recommended next task

**Phase 4 — the NPC agent tier (D-003).** TASKS.md order, nothing blocking it. The Acolyte
languages gap above would make a clean warm-up if a session wants one.

---

## 2026-08-15 (k) — the API key is now project-specific (Claude Code, kelly-pc)

**No code. Operational, and one gotcha worth the entry.** Nothing in the repo changed;
`3e63802` is still HEAD and everything is pushed. **The next task is unchanged: the
backgrounds ruling** — see the (j) entry below for the full spec.

Kelly rotated the Anthropic key because something unidentified was pulling from a shared
one, and is now giving each project its own explicit key and letting the rest break to
find the consumers. `C:\dev\dnd-campaign\.env` holds a dedicated key for this project.
Verified live: `dndc gm --billing api` returned narration, $0.0218.

**The gotcha, which cost a false pass before it was caught.** `load_env_file()`
deliberately never overrides an existing environment variable — its docstring says "a
real environment variable always wins", which is right in general and a trap here. An
ambient `ANTHROPIC_API_KEY` (a user-level Windows variable, or one inherited by a
long-running process that started before it was removed) **silently shadows `.env`**, and
the CLI reports a confident success while billing the wrong key. Caught by comparing
fingerprints of the ambient value and the file value rather than by running the check and
believing it.

So: if a key ever seems wrong here, check the ambient variable before touching `.env`, and
test from a **freshly started** shell — a process started before the variable was removed
keeps its stale copy.

**Two things that will not announce a bad key here**, and they are worth knowing before
someone debugs the wrong thing:

- **Subscription mode does not use the key at all.** D-004's credential isolation strips
  `ANTHROPIC_API_KEY` from the child environment, so `dndc play` on the sticky default
  works perfectly with no key present. Absence of breakage proves nothing; force
  `--billing api` to test.
- **`--billing api` is sticky.** Passing it rewrites `config.yaml` line 5, so a one-off
  test silently changes the default for every later session. Restored to `subscription`
  after the check, which is Kelly's standing choice.

### Recommended next task

**Unchanged — the backgrounds ruling (option 3).** Full spec in the (j) entry below.

---

## 2026-08-15 (j) — the date correction, and monster tactics become the GM's (Claude Code, kelly-pc)

**Fable's date correction applied, and the tactics ruling implemented. 1059 tests, suite
still fully offline.** The backgrounds ruling is **not** implemented — it is the next task.

### The dates were confabulated, and Fable was right

Nine entries claimed dates that never happened. Checked against `git log` rather than
argued about:

| entry | claimed | commit | actual |
|---|---|---|---|
| seat split | 08-15 | `1547112` | **08-14 23:33** → 08-14 (b) |
| P2.6 | 08-15 (b) | `cff1019` | 08-15 01:52 → **08-15** |
| ingest | 08-16 | `aff8c20` | 08-15 02:13 → **08-15 (b)** |
| drift baseline | 08-17 | `4095af0` | 08-15 02:37 → **08-15 (c)** |
| P3.1–P3.6 | 08-18…08-23 | `9fc3425`…`9e21b50` | all 08-15 → **(d)…(i)** |

Every affected date is corrected — headings, in-entry references, TASKS.md completion
notes, the D-008 amendment for P3.3, and the code comments citing it. Root cause was
exactly as diagnosed: the clock stopped advancing in my context and I kept incrementing
from the last one I had seen, which is inference wearing a date's clothes. CLAUDE.md now
says entry dates come from the system clock; I read it with `date` this session, which is
how I know today is 08-15 and this entry is (j).

Worth saying plainly: **the drift instrument's own log had confabulated provenance in it.**
That is the failure mode this project exists to study, committed by the thing studying it.
The correction is cheap; noticing it was Fable's.

**A related catch while fixing it:** my own correction script double-applied — the
sentinel guarding a rewritten date sat *after* the match, so `2026-08-15` still matched as
a prefix of `2026-08-15\0` and got shifted a second time. Caught by reading the output
rather than trusting the script, which is the same lesson one layer down.

### Monster tactics: the GM chooses, the engine logs it

Per the 2026-08-15 (c) ruling. D-008 amended first.

`[[TARGET: <monster> -> <target>]]`, declared **a turn ahead** in the narration call that
already happens — which is what makes it cost nothing, and the GM is better placed to say
who the wolf goes for next having just been shown the state. `combat_turn` gains `target`
and `target_source`.

The third value of `target_source` is the one worth having. A declaration written ahead
can be overtaken — the named target may be down by the time the turn arrives — so:

- **`declared`** — the GM chose and the engine honoured it;
- **`policy`** — nothing declared, deterministic fallback, *logged as a fallback*;
- **`stale`** — a declaration that expired, fallback ran.

"The GM chose badly" and "the GM's choice expired" are different findings, and a fight
must never stall on a missing tag. A declaration is consumed on use rather than standing,
because a standing order would go stale silently — which is the exact failure this design
exists to make visible.

**One small generalisation fell out:** `resolve_member` (shared by `/switch`,
`/inventory`, the inventory store and now this) assumed every candidate has a `player`
field. Monsters do not. It now searches whatever identifying fields an object actually
carries.

### Live run

`dndc combat --monster wolf*2 --billing api --seed 5`. The log reads:

```
r1 wolf-2  -> brother-hammond  [declared]
r1 wolf-1  -> corin-vale       [policy]
```

The GM had the wolf Hammond had just hurt turn on Hammond — which is precisely the monster
personality the ruling was for, and something the most-wounded policy would never produce.
The tags never appeared in the narration. Billing was set to `api` for the run and
restored to `subscription` afterwards.

### Known issues

- **The backgrounds ruling is unimplemented** — co-creation proposes an original
  background, engine validates the shape, table confirms, filed as campaign data. It is
  the next task and nothing here touches it.
- Declarations are per-turn and only for monsters; a player's target is still their own
  choice at the prompt, which is right.
- The GM has no way to declare anything *other* than a target — no "the wolf disengages",
  no "the captain shouts an order". Movement and non-attack actions are unmodelled in the
  turn loop, so there is nothing for such a tag to mean yet.

### Recommended next task

**The backgrounds ruling (option 3)**: co-creation proposes an original background, the
engine validates its shape deterministically (exactly two skills from the standard list,
≤1 tool or language, **never** numeric bonuses), the proposal must not duplicate the class
skill picks (the P1.4 double-granting trap), the table confirms, and confirmed backgrounds
persist beside `canon.yaml` for reuse. Acolyte stays as the one SRD row. Kelly holds
content veto.

---

## 2026-08-15 (i) — P3.6: the combat view, and Phase 3 closes (Claude Code, kelly-pc)

**P3.6 done. Phase 3 complete. 1042 tests, suite still fully offline.** No new rulings;
both open questions are still Fable's and untouched.

### The view owns the numbers

`render_encounter`, `hp_bar`, `choose`, `player_turn`. Initiative order, hit-point bars,
conditions, whose turn it is — rendered from state, never from anything a model said.
That is the other half of OD-11: the GM's silence about numbers is only safe because this
exists, so the display has its own tests rather than being eyeballed.

One rule the bar breaks on purpose: **a living combatant never shows an empty bar.** One
of forty rounds to zero twelfths, and an empty bar beside a living character is the
display contradicting the number printed next to it. Anything above zero keeps at least
one block.

### Weapons come off the sheet, which is P2.4 paying off

`weapons_for` derives every number rather than choosing it: the ability from the weapon's
own properties (ranged uses Dexterity, finesse takes the better of the two, everything
else Strength), proficiency from what the sheet says the character is trained in, damage
from the SRD entry. Against the real party that gives Corin a Rapier at +5 for 1d8+3
piercing and Hammond a Warhammer at +5 for 1d8+3 bludgeoning, which is correct 5e and was
previously a hardcoded "weapon, +5, 1d8+3, slashing" in the demo runner.

A weapon the character is *not* trained in still swings — they simply do not add the
bonus, which is the rule rather than an error. Someone carrying nothing gets an unarmed
strike.

### Three bugs, two of them mine and one worth remembering

**The active marker never moved and every render showed end-of-round state.** The CLI was
rendering from `run_round`, which returns a *finished list* — so all the turns were over
before the first line was drawn. My own docstring on that function says the CLI should
drive `take_turn` itself; I had not followed it. Now it does, and the view updates once
per round with the state that was actually true.

**Rich ate the conditions.** `[prone]` is markup to rich, so a condition sitting correctly
on a combatant vanished silently from the display. Parentheses now. Worth remembering
because it fails *quietly* — nothing errored, the information just was not there.

**My live run reverted Kelly's billing preference.** `--billing api` counts as choosing,
and D-004's sticky default duly saved it — overwriting the `subscription` she had set. I
used `api` deliberately so the cost figure below is a legitimate campaign claim under
OD-16, then restored the config to `subscription`. Flagging it because the same thing will
happen to anyone who passes the flag once: **the sticky default is stickier than it
looks.**

### The live run

`dndc combat --campaign the-salt-road --difficulty hard --billing api --seed 11`. The
builder produced 2× Swarm of Ravens (140/160 XP), the party swung their real weapons, and
the narration tracked the severity bands faithfully: "wounded" came out as hurt but far
from finished; "dropped" as *"she simply goes down, swallowed in the churning mass of
wings, and doesn't get up."* No number appeared in any of it. **5 GM calls, $0.043** —
an `api` run, so that figure is quotable.

### Phase 3 is complete

A deterministic combat core; SRD stat blocks turned into combatants; an event vocabulary
that reused what already existed rather than growing; a turn loop where the fight is
decided and logged before the GM sees it; an encounter budget measured against the engine
rather than asserted; and a view that owns the numbers.

### Known issues

- Conditions are displayed but still barely act — `prone`, `grappled` and `restrained`
  change attack rolls and movement and nothing consults them. That is a rules gap, not a
  view gap, and it is the most obvious thing left in combat.
- A player's turn is one attack at one target: no movement, no spells, no dodge or dash,
  no bonus actions. The action economy exists in the engine and the interface only offers
  the attack.
- Multiattack for player characters (Extra Attack at level 5) is unmodelled.
- The two open questions stand: monster tactics, and backgrounds.

### Recommended next task

**Phase 4 — the NPC agent tier (D-003)**: NPC schema with voice card and knowledge scope,
per-turn prompt rebuild by the GM director, the gatekeeper pass, and stance-scoped
supersession ported from the mystery. It is the last major architectural tier and the one
the whole canon-scope design (P2.1's `gm_only` and `npc_belief`) has been waiting for.

---

## 2026-08-15 (h) — P3.5: an encounter budget we had to invent, so we measured it (Claude Code, kelly-pc)

**P3.5 done. 1015 tests, suite still fully offline.** No new rulings; both open questions
(monster tactics, backgrounds) are still Fable's and untouched.

### The SRD has no encounter-building tables

Checked before designing, and it is the same shape as the Acolyte finding: the XP
thresholds by character level and the multiplier for a group are **DMG content, outside
D-007's CC-BY licence**. The ingested set has neither. What the SRD does give is every
monster's `xp` and `challenge_rating`.

So the budget had to be ours. The choice was between inventing coefficients and calling
them a budget, or **measuring them** — and this project happens to have a deterministic,
free, model-free fight engine sitting right there. A budget you can test is worth more
than a budget you can cite.

`simulate` runs thousands of mechanics-only fights and reports win rate, "someone went
down" rate, death rate and median rounds. "Deadly" now means *the party actually loses
this often*, not a label.

### It found two real errors, which is the point

**Filling greedily from the biggest affordable monster prices encounters backwards.** One
large monster against four characters gets one turn to their four and loses; my first pass
had `hard` (Hell Hound + weasel, 12% someone down) come out *easier* than `medium` (giant
constrictor, 28%). Action economy dominates at these levels, and a builder that ignores it
is not approximately right, it is inverted. The builder now chooses **how many before
which**, near the party's size.

**A swarm needs a far steeper group multiplier than XP suggests.** Six dretch — 150 XP —
beat four level-1 characters 93% of the time, while two giant eagles at 400 XP lost more
often than they won. A flat sum, or the gentle 2.0× I started with, prices a swarm as a
pushover.

### What the bands actually measure (200 fights per cell)

| party | easy | medium | hard | deadly |
|---|---|---|---|---|
| 4× lvl1 | 100% win, 0% down | 100%, 16% | 100%, 52% | **48%**, 94% down, 46% died |
| 4× lvl3 | 100%, 5% | 99%, 69% | 97%, 76% | **48%**, 98%, 48% died |
| 4× lvl5 | 100%, 6% | 96%, 72% | 70%, 94% | **9%**, 100%, 74% died |
| 2× lvl1 | 98%, 16% | 100%, 4% | 45%, 76% | 62%, 67% |

Monotonic and sensible for four-character parties. **Two honest problems**, both reported
rather than tuned away:

- **The two-character row is not monotonic** — `hard` came out harder than `deadly`. Small
  parties plus coarse monster granularity means the builder cannot hit the budget finely.
  This is the row that matters most here, because Kelly and Sam are a two-person table.
- **`deadly` is over-lethal at level 5** (9% win). The band multiplier wants lowering, and
  I would rather say so than quietly fit it.

### The simulator's limits, which bound every number above

The simulated party swings a plain weapon for slashing damage, with no healing, no spells,
no positioning and no tactics; the monsters attack the most wounded. That is much cruder
than a real party, so these bands describe *that* model. The clearest demonstration came
free: `4× Ochre Jelly` scored 0% wins — ochre jellies are **immune to slashing**, and a
party that only deals slashing cannot hurt them at all. No XP budget can price that, and
no amount of coefficient-fitting would have found it.

Chasing the bands further would have been fitting numbers to a bad model. The builder and
the simulator are solid; the coefficients are provisional and now have data behind them.

### Known issues

- Bands provisional, per the table above. The simulator is checked in, so refining them is
  a measurement rather than a guess.
- A group is one monster repeated — a pack, which is what the count is for. Mixed groups
  are the caller's to assemble from several plans.
- Damage-type coverage is unmodelled on both sides, which is what the ochre jelly case
  exposes. A party's real damage types live on sheets and weapons; wiring that in is P3.6
  territory at the earliest.

### Recommended next task

**P3.6 — the rich combat CLI view**, and the last task in Phase 3: initiative order, HP
bars, conditions, whose turn it is, and a player finally *choosing their own action*
instead of the demo runner's generic weapon. That is also where real weapons come off the
sheet, which is the first step toward the damage-type gap above.

---

## 2026-08-15 (g) — P3.4: the combat turn loop (Claude Code, kelly-pc)

**P3.4 done. 993 tests, suite still fully offline.** No new rulings; the Acolyte question
from 08-16 is still open and untouched.

`game/combatturn.py`, `gm/prompts/combat.md`, and a demo runner (`dndc combat --monster
wolf*2`) so the thing is live-runnable — which the live-run rule requires of anything
model-facing.

### Resolve, log, narrate — in that order

The fight is fully decided and written down before a model sees any of it. Two things fall
out of that ordering, and both are tested: a narration **cannot** change an outcome, and a
session that loses its GM mid-fight still has a complete and correct combat log. The
pending/terminal discipline from OD-9 holds here too — a failed narration still writes its
terminal row.

**The GM is handed severity words and no integers**, measured against the target's own
maximum, because six damage is a scratch to a barbarian and nearly lethal to a level-1
wizard. This is OD-12 at full strength: the model cannot restate a value it was never
given. There is a test asserting no digit appears in anything the engine says about the
fight.

### FOR DESIGN: who chooses monster tactics?

**Deterministic, for now** — the most wounded standing enemy, ties by initiative order.
Stated in `choose_target` and dull on purpose.

The argument for keeping it out of the model is strong and I want it on the record: **a
model choosing targets makes a fight unreplayable**, and replay-from-a-seed is the property
the whole combat core was built for. A logged fight that cannot be re-run is not evidence
of anything.

The argument against is also real: target selection is *judgment*, not arithmetic, and
D-001 puts judgment with the GM. A wolf pack that always focuses the most wounded plays
like a machine — which it is.

Middle ground if Fable wants tactics to be a GM call: **let the GM choose and log the
choice**, so a replay reads the decision from the log rather than re-asking the model. That
keeps reproducibility and buys back the judgment, at one extra call per monster turn. I
have not built it — this is a "how should the game feel" question, not an engineering one,
and nothing is blocked either way.

### Two bugs the live run found

Both are the kind only a real run surfaces.

**A dead monster was being described to the GM as "unconscious and dying".**
`damage_severity` says that for anything at zero, which is right for a character and wrong
for a monster — monsters do not make death saves. The GM would have narrated a wolf on the
floor as still breathing. Fixed where the knowledge lives, in the turn engine, so
`rules/severity.py` stays general.

**Death saves happened silently.** A dying character gets a turn precisely so the save
happens, and the turn was producing no output at all. Now it says so in words — "holds
on", "slips further", "stops breathing" — with no tally, because the numbers belong to
the interface.

And one hang, which was my own test's fault and the massive-damage rule working correctly:
99 damage to a 24 HP character is instant death, not dying, so `advance()` never stopped on
them and the test's `while` spun. It did reveal a real hazard, though — `run_round` waited
on the round counter to tick, and `advance()` deliberately stays put when nobody can act.
That loop is now bounded by the size of the order.

### The live run

`dndc combat --campaign the-salt-road --monster wolf --seed 21`, real GM seat, ~$0.03 for
four narrated turns. It reads like the game: misses stay misses, and the kill was narrated
as a kill ("dead before it hits the frost-hard ground") rather than as a swoon. Log checked
— one `combat_start` with the roster and seed, four `combat_turn`, one `hit_point_change`
(`11→0, killed=True`), one `combat_end` (`party`, 2 rounds, both survivors), four `cost`
rows.

Mechanics-only runs are free (`--no-narration`), and two level-1 characters against two
wolves is reliably lethal, which is correct 5e and worth knowing before a real table
meets one.

### Known issues

- **Narration is per turn, so three consecutive misses get three paragraphs.** A human GM
  would batch them. Fixable by narrating per round instead, at the cost of the GM losing
  the ordering; worth revisiting in P3.6 when there is a view to judge it against.
- The demo runner gives every player character a generic "weapon" at +5 for 1d8+3, so the
  GM invents what they are swinging ("Corin's dagger", "Hammond drives his sword"). Real
  weapons come from the sheet — that is P3.6's, along with asking a player what they want
  to do.
- Conditions still barely act: `prone`, `grappled` and `restrained` change attack rolls and
  movement and nothing consults them yet.
- Saving-throw actions (a breath weapon) build an `Attack` with a DC and the turn loop has
  no path for them — every monster below CR 5 that matters uses attack rolls, so this has
  not bitten, and it will above CR 5.

### Recommended next task

**P3.5 — the encounter builder** on a CR/XP budget, drawing on the 245 ingested monsters.
It is the smaller of the two remaining and it makes P3.6 worth building, since a view
wants something to show. Then **P3.6**, the rich combat CLI view — where a player finally
chooses their own action and the authoritative numbers get their proper display (OD-11).

---

## 2026-08-15 (f) — P3.3: the combat event vocabulary (Claude Code, kelly-pc)

**P3.3 done. 968 tests, suite still fully offline.** No new rulings; the Acolyte question
from 08-16 is still open and untouched.

D-008 amended first, as its own rule requires — and written *after* P3.1 and P3.2 existed
rather than alongside them, which was the whole reason P3.3 was scheduled third. There was
a real fight to describe instead of a guess at one.

### The best outcome was fewer families, not more

`rules_resolution.kind` was specified on 2026-07-27 as
`check | save | attack | damage | initiative | roll`. It already covers every die a fight
rolls, and the family already carries `actor`, `target`, `dc` (a target's AC *is* a DC),
`critical` and `seed`. So **attacks, damage rolls, death saves and initiative added no
family at all** — a death save is a save against DC 10 with no ability and no proficiency,
which is exactly what the rules say it is.

Four are genuinely new (D-008 items 9–12): `combat_start`, `combat_turn`,
`hit_point_change`, `combat_end`. Each earns its place on a specific question:

- **`combat_start`** carries the roster *as instantiated*. Monster hit points may be
  rolled (P3.2), so without it every later row refers to a creature of unknown durability
  and the fight cannot be read, let alone replayed.
- **`combat_turn`** is derivable in principle from the order and the rows between.
  Derivable-in-principle is where analysis goes wrong, and Phase 7 will ask which round a
  narration happened in.
- **`hit_point_change`** is the `inventory_change` argument exactly: the engine performing
  a change to a sheet the GM must never invent. It is separate from the roll because the
  two come apart — a fall damages with no attack roll, and resistance changes what a roll
  means without changing the roll.
- **`combat_end`** makes a fight's length and lethality queryable, which is most of what
  Phase 3 exists to make measurable.

Separate types rather than one `combat` family with a `phase` field, so pydantic makes a
wrong-shaped row unrepresentable rather than merely discouraged — the OD-11/OD-12 stance
applied to a schema.

**Deliberately not added: `condition_change`.** Nothing emits it; conditions barely act
until P3.4. A family nothing writes is vocabulary ahead of code, which is the failure this
task's own scheduling was chosen to avoid.

**Which fight a roll belongs to** went in `rules_resolution.detail["encounter"]` rather
than a new field. Three of the six `kind` values never occur in combat, and widening a
family shared with every check in the game for something only combat needs is the wrong
trade. Documented in the amendment so it is a decision rather than an undocumented habit.

### The vocabulary was checked against a fight, not against itself

`game/combatlog.py` — a recorder that watches an `Encounter` and writes the rows.
`rules/combat.py` stays pure and cannot log, which is what keeps a fight reproducible; the
recorder decides nothing and every number it writes was handed to it.

The test that matters plays a real fight (a character and two SRD wolves), logs it, and
then asks the log what happened **without re-simulating**: the roster reconstructs, every
damage row points at a real combatant and at the roll that caused it, and summing the
damage per combatant agrees with the final hit points.

That last assertion caught a genuine bug. `DamageOutcome.taken` is the damage applied
*before* the floor at zero, so a 31-point hit on a character with 24 left was writing
`amount: 31` on a row whose own `before` and `after` differed by 24. A row that disagrees
with itself is worse than a missing one, and every sum over the log would have inherited
it. `amount` is now `before - after`, with the excess still recoverable from the damage
roll.

`DamageOutcome` also gained `damage_type` — the recorder was about to write `None` for
every hit, and whoever records a change should not have to be told what was just applied.

### Known issues

- **Nothing calls the recorder in play yet.** That is P3.4 — there is no combat turn loop,
  so the only thing that has ever written these rows is a test. The vocabulary is
  validated against a real fight, not against a real *session*.
- `INITIATIVE` is defined as a `kind` and unused: the order is logged once in
  `combat_start`, which is more useful than a row per roll. The constant stays because
  P3.6's CLI view may want to show individual initiative rolls.
- `combat_start.round` is always 1. It exists for a fight resumed mid-way, which is Phase
  5's business.

### Recommended next task

**P3.4 — the combat turn loop.** Where D-001's boundary takes its real load: the engine
resolves, the GM narrates what it is handed, players act through the CLI, and the recorder
finally runs in anger. It also has to decide what a turn does with the 41 unresolved
multiattacks from P3.2 — most likely show the text and let the table say, because falling
back to one attack is the quiet wrong answer.

---

## 2026-08-15 (e) — P3.2: stat blocks become combatants (Claude Code, kelly-pc)

**P3.2 done. 951 tests, suite still fully offline.** No new rulings; the Acolyte question
from 08-16 is still open and untouched.

`src/dndc/rules/statblock.py` — `from_monster` and `from_sheet`. Still pure: data in, data
out, no repository, no disk, no model. 245 SRD monsters and any character sheet can now
walk into the P3.1 fight engine.

### The SRD is prose in two places, and both refuse to guess

This is the whole shape of the task. The easy version of P3.2 is an afternoon; the version
that does not put wrong numbers in front of players took the day.

**Multiattack is a sentence.** I measured before designing: of 68 monsters with one, 14 are
the trivial "makes two slam attacks", 21 are colon-lists ("two attacks: one with its beard
and one with its glaive"), 18 offer alternatives ("*Or* the captain makes two ranged
attacks"), 15 carry conditionals. The parser takes the first two shapes and refuses the
rest — **27 resolved, 41 unresolved**, the unresolved ones carrying their text and, where
the sentence says so, their count. An alternative is not a parsing problem, it is the
engine being asked to choose the monster's tactics, which is the GM's call.

The colon-list is deliberately **all-or-nothing**: if any named part fails to match a real
action, the whole thing stays unresolved. A partly-resolved multiattack is a monster with
the wrong number of attacks, which is worse than one the caller knows to ask about. I
eyeballed all 27 resolved ones and they are correct.

**Damage modifiers are sometimes qualified.** Four distinct strings read like "bludgeoning,
piercing, and slashing from nonmagical weapons" — 92 monsters carry one. Whether it applies
depends on the weapon swinging, which a stat block cannot say. Applying them blindly would
roughly **double a monster's effective hit points** against an ordinary party, so they are
recorded in `qualified` and left unapplied. There is a dataset-wide test asserting no
monster ever gains blanket physical resistance by accident.

### A bug I caught in my own code before it ran

`_condition_immunities` was writing a monster's immunities into `Combatant.conditions` —
the set of conditions it *has*. A monster immune to being knocked prone would have been
marked as lying on the floor. `Combatant` gained a `condition_immunities` field, and
`with_conditions` now honours it at the one place conditions change, with `unconscious`,
`dead` and `stable` exempt: those are what the engine does when hit points run out, not
conditions inflicted on a creature, and a monster immune to being knocked out still dies.

### Known issues

- **41 multiattacks are unresolved and nothing consumes that yet.** P3.4 has to decide
  what a turn does with `resolved=False` — most likely show the text and let the table
  say. Falling back to one attack would be the quiet wrong answer.
- **`qualified` is recorded and unread.** Applying it needs to know whether an attack is
  magical, which needs weapons to carry that property — not modelled, and not needed until
  something in the party has a magic weapon.
- Legendary actions, reactions, and recharge (`usage`) are ingested and ignored. None of
  them matter below CR 5, which is the ingest scope.
- Saving-throw actions build an `Attack` with a DC, but nothing resolves one yet — the
  engine has `resolve_save`, and wiring it is P3.4's.

### Recommended next task

**P3.3 — the combat event vocabulary, doc-first per D-008.** It is next precisely because
P3.1 and P3.2 now exist: there is a real fight to describe rather than a guess at one. The
question it has to answer is which parts of a fight are `rules_resolution` (an attack
roll, plainly) and which need their own families (round boundaries, initiative order,
hit-point changes, a monster dying). Amend D-008 first, then write code.

---

## 2026-08-15 (d) — Phase 3 opens: the deterministic combat core (Claude Code, kelly-pc)

**Phase 3 broken into tasks, and P3.1 done. 916 tests, suite still fully offline.** The
background question from 08-16 is still open and untouched.

### Phase 3 has a task breakdown now

It didn't. Every other phase does, and "combat" as one unit is several sessions. P3.1
core → P3.2 monsters from stat blocks → **P3.3 the event vocabulary, doc-first** → P3.4
the turn loop → P3.5 encounter builder → P3.6 the CLI view.

P3.3 is deliberately *third*. Guessing what a fight emits before one has ever run is how
a vocabulary ends up describing the code instead of the game, and D-008's own rule is
doc-first, not doc-blind. An attack is probably a `rules_resolution`; round boundaries,
initiative order and hit-point changes are probably not. I would rather answer that after
P3.2 exists than commit to it now.

### P3.1 — every number in a fight

`src/dndc/rules/combat.py`. This is the phase D-001 was written for, and the property
worth stating first: **nothing in the module can reach a model.** No logging, no disk, no
network. So there is no live run to do — the test suite is the entire verification, which
is the first time that has been true since Phase 0.

Two decisions where the easier answer was wrong:

**Combatants are frozen; every change returns a new one.** A fight is a sequence of
states, not an object being mutated, and holding two at once is what lets a caller show
before-and-after without bookkeeping. It also means a half-applied turn cannot exist.
`Encounter` is the one mutable thing, because threading the bookkeeping through every
caller would put it in every caller.

**Initiative ties break deterministically** — dexterity, then side, then name, never a
re-roll. 5e hands ties to the DM, which is right at a table and useless in an instrument:
the same seed and the same combatants must produce the same order, or a replayed fight is
not the fight that happened. There is a test that plays a whole fight twice from one seed
and compares transcripts, and a second test asserting different seeds *do* diverge — so
the first cannot pass by nothing being random at all.

Also in, because each is a rule that is easy to get subtly wrong and quietly play without:
resistance/vulnerability/immunity with 5e's precedence (immunity wins; resistance and
vulnerability cancel), temporary hit points spent before real ones, massive damage killing
outright, a hit on a dying character counting as a failed death save, and a natural 20 on
a death save being a *recovery at 1 HP* rather than a success.

**A dying character still gets their turn.** Skipping them would be the obvious
optimisation and would quietly delete the tensest thirty seconds in 5e — the death save
happens on their turn.

### One bug the tests found

A combatant dropped *during their own turn* — by a reaction, a trap, ongoing damage — kept
the rest of their action economy. Fixed at `replace_combatant`, the single point state
changes through, so no caller can forget it. That choke-point habit has now caught
something in three separate modules.

A sample fight, to show it plays like the game rather than merely computing:

```
order: ['Wolf', 'Bandit', 'Corin Vale', 'Hammond']
r2 Wolf hits Corin Vale -> 0hp      (drops, starts saving)
r2 Corin Vale death save 8          (fail)
r3 Corin Vale death save 5          (fail)
r4 Corin Vale death save 4          (dead)
r5 Bandit hits Hammond -> 0hp
winner: foes
```

### Known issues

- **Conditions are declared but barely act.** `prone`, `grappled` and `restrained` are in
  the enum and nothing consults them — they change attack rolls and movement, which is
  P3.4's business once there is a turn loop to apply them in. `incapacitated` and
  `unconscious` do work, because the state machine needs them.
- **No concentration, no reactions-in-practice, no multiattack.** Reactions have a budget
  slot and nothing spends it yet; multiattack is P3.2, where monster actions arrive.
- The combat core does not know about `CharacterSheet` yet — a `Combatant` is built by
  hand. Wiring sheets and SRD stat blocks into combatants is P3.2.

### Recommended next task

**P3.2** — monster instantiation from SRD stat blocks: a `Monster` (245 of them ingested,
CR 0–5) becomes combatants with rolled or average hit points, its `actions` become usable
attacks, and multiattack is understood. That is also what gives P3.3 something real to
design a vocabulary against.

---

## 2026-08-15 (c) — the drift baseline: the fixture, not the seed (Claude Code, kelly-pc)

**Fable's 2026-08-15 ruling implemented. 866 tests, suite still fully offline.** The
background question from 08-16 is still open and untouched — it is a content decision and
nothing here depends on it.

### What landed

`data/drift/*.baseline.yaml` — one committed artifact per archived session, carrying the
recovered canon plus how it was recovered: model, temperature, seed, date, `dndc` version,
commit, and the **SHA-256 of the source log**. That last field is the one that earns its
place: an archived log edited or replaced after the fixture was cut would otherwise show up
as the world mysteriously drifting, and now it reports "baseline is stale — re-record it".

`dndc drift` became three operations, because they are three genuinely different things:

- **`check`** — survival against the committed baselines. **No model, no NAS, no logs.**
- **`record`** — cut a baseline. The expensive, model-touching half; refuses to overwrite
  without `--force`, because a baseline quietly re-cut is a measurement that moved without
  anyone deciding it should.
- **`measure`** — the model-assisted half: contradiction frequency, plus the recovery
  stability diff against the fixture.

### The part that pays off most

With the canon in a file, **survival stopped being an errand and became an assertion**. It
is now a test (`test_the_committed_baselines_all_survive`) that runs in milliseconds with
the GPU box off and the NAS unmounted. Phase 2's central claim — established facts reach
the next session's prompt — is checked on every `pytest` run rather than when someone
remembers to point a command at the NAS. **206 facts across two baselines, all surviving.**

### The seed: measured, and it makes the ruling's case better than the ruling did

Fable allowed a seed as a tightener and warned it is hostage to model version and server
internals. I added it and measured it, and the numbers are sharper than expected:

- **Same seed, back to back: byte-identical.** Three runs of the 11-turn log at seed
  20260815 gave the same 15 facts every time; two runs at seed 999 gave the same 21.
- **Different seed: a different world.** 37% vs 11% stability against the same baseline.
  The seed is not a small perturbation — it changes which facts are found.
- **Same seed, different server state: not reproducible.** The 11-turn log recorded
  *alongside another log* gave 19 facts; recorded alone, 15 — same seed, same temperature,
  same model, same input. Recovery is a **chain** (each turn's sweep prompt carries the
  ledger built so far), so one divergence cascades through everything after it.
- **And it degrades with length.** Re-measuring immediately after recording: **100% stable
  over 11 turns, 63% over 32.** Deterministic run-to-run (63% twice, identical breakdown),
  just not across the recording state.

So a seed buys repeatability within one process on one machine and buys nothing across
them. That is exactly why the fixture is the answer, and I would not have been able to say
so with numbers if the ruling had not told me to add the seed anyway.

**Procedural note for whoever cuts the next baseline: one log per invocation.** Both
committed baselines were re-cut that way after the finding above.

### Recovery stability is now its own number

`compare()` diffs a fresh sweep against the fixture and reports **identical / reworded /
missed / new**. Two readings rather than one on purpose: *identical* is whether the model
said the same words, *equivalent* is whether it found the same fact, and collapsing them
would hide which happened. A one-to-one match is enforced, so a sweep that collapsed three
facts into one cannot score as stable.

### Known issues

- **The baselines contain scene noise.** "The guard has sized up Hammond and is now sizing
  up Corin" is in there as a `player_known` fact. That is the sweep's known volume problem
  (Fable's standing observation: act when the table finds confirmation fatiguing, not on a
  number in a log), and for a *baseline* it is harmless — the fixture's job is to be fixed,
  not to be good. Worth knowing before anyone reads one as a curated world.
- `commit_sha` in both baselines ends `-dirty`: they were cut from an uncommitted working
  tree, which is truthful and slightly unfortunate for a committed artifact. Re-cutting
  after the commit would only move the problem, since the SHA would then predate the
  baselines it stamps.
- The 32-turn baseline is 1,093 lines of YAML. Fine at two sessions; worth watching if this
  becomes a per-session habit rather than a fixed set of before-pictures.

### Recommended next task

**Phase 3 — combat.** Initiative tracker, action economy, SRD monster stat blocks,
deterministic resolution with GM narration layered per round, encounter builder on a CR
budget. It is the first phase since Phase 0 where the deterministic core does the heavy
lifting and the model narrates around it, which is D-001's boundary under the most load it
has seen.

---

## 2026-08-15 (b) — backgrounds, starting equipment, and the weight gap (Claude Code, kelly-pc)

**The scheduled ingest task is done. 845 tests, suite still fully offline.** Fable's
2026-08-15 drift-fixture ruling is implemented **not at all** — see the scope note at the
end; it is the next task.

Three gaps closed, all of them things that had been true since 08-05 and had stopped being
cosmetic now that Phase 3 is combat.

### Backgrounds grant something

`background` was a string on the sheet. It is now an SRD type: ingested, referentially
validated, exposed on the repository, and granted by `build_character` — skills, tool
proficiencies, and a starting kit. `grant_issues` checks it too, for hand-edited sheets and
for every character built before this existed.

A class pick that duplicates a granted skill is **refused back to the GM**, not silently
merged. 5e's answer to the clash is to choose something else, and merging would leave the
character quietly a proficiency short. The objection goes to the GM rather than the player,
per D-005.

**FOR DESIGN: the SRD contains exactly one background — Acolyte.** Soldier, Sage, Criminal
and the rest are PHB, outside D-007's CC-BY licence, and must never be ingested. So the
mechanism is complete and the dataset has one row: Corin Vale is an "Urchin" and always
will be, mechanically inert. Three options, and this is a content decision rather than an
engineering one:

1. **Leave it.** Backgrounds stay flavour except for Acolyte. Costs nothing, and the
   sheet is honest about granting nothing.
2. **Author original backgrounds as campaign data** — a `backgrounds.yaml` beside
   `canon.yaml`, same schema, table-authored. Legitimate under D-007 (original content is
   the whole premise) and it makes the mechanism worth having.
3. **Let co-creation propose one** and file it as campaign data on confirmation, the way
   canon and inventory already work.

I have built none of them. An unknown background resolves to `None` and stays flavour,
which is the correct behaviour under all three, so nothing is blocked either way. I put a
test in the repo asserting the count really is one, so a future session does not "fix" it
by reaching for the PHB.

### Weights are real now

Starting equipment used to be raw SRD indices at 0 lb — a sheet read `rope-hempen-50-feet`
weighing nothing. It now resolves through the repository, so items carry the ruleset's
spelling and weight. A cleric who put a live build through this comes out at **69 lb**
instead of the armour's 55.

Same fix reaches **P2.4's known gap**, which Fable explicitly paired with this task:
`apply_gain` takes an optional `catalogue` callable, and `InventoryStore` backs it with the
repository. So an item picked up in play now weighs what it weighs, and the ruleset's
spelling wins — "a rope" and "Rope, hempen (50 feet)" stop being two piles.

`rules/inventory.py` stays a pure function over a list; the catalogue is passed in, never
imported. Something the ruleset has never heard of still lands on the sheet and weighs
nothing: a keepsake is not equipment, refusing it would be the sheet contradicting the
fiction, and a fabricated weight would be worse than an absent one.

### Known issues

- **52 of 237 SRD equipment entries have no weight upstream, including every equipment
  pack.** An Explorer's Pack is the commonest starting item there is and the SRD gives it
  no figure (it lists contents instead). So `carried_weight` is now much better than
  zero-for-everything and still under-reports. Deriving a pack's weight from its prose
  contents is inventing a number the SRD declined to give, so I have not.
- The creation prompt does not know backgrounds grant anything, so the GM will not
  propose Acolyte for the mechanical reason. Only worth fixing alongside a decision on
  the `FOR DESIGN:` above.

### Scope note: what I did not do

Fable's 2026-08-15 ruling ("the drift baseline: the fixture, not the seed") says it **may**
ride with this task. It did not. This commit already spans the SRD schema, ingest,
validator, repository, character build, the rules core, the inventory store and the CLI;
adding a second, unrelated instrument change would have made it unreviewable and blurred
two things that want separate scrutiny. Permission is not obligation, and one session one
commit is the standing rule. Flagging it rather than leaving it to be noticed.

### Recommended next task

**The drift-baseline fixtures**, per the 2026-08-15 ruling: recovered-canon artifacts for
both archived sessions checked into the repo with generation metadata (model, temperature,
date, source-log hash), the baseline running against those, and the two measurements split
— fixture→prompt is survival (deterministic), re-sweep-and-diff is recovery stability.
Then Phase 3.

---

## 2026-08-15 — P2.6: the drift test, and Phase 2 closes (Claude Code, kelly-pc)

**P2.6 done. Phase 2 complete. 823 tests, suite still fully offline.** No open decisions;
the 08-14 rulings were all implemented earlier today.

D-002's rationale says that "without the ledger, established facts mutate within one
session". That has been the premise of the whole phase and it was never a measurement.
Now it is one.

### What was built

`src/dndc/analysis/` — a new package, and the first code in this repo that runs over logs
rather than during play. Nothing in it writes to a campaign or to a session log; an
instrument that alters what it measures is not an instrument. `dndc drift LOG...` is the
entry point, `--no-scan` for the deterministic half alone.

- **`replay.py`** — a logged session back into `Turn`s. This existed as a throwaway script
  three separate times before it existed as a module, which is the repo saying where it
  belonged. Narration is cleaned with exactly the three strippers `turn.py::_clean` uses;
  if they ever disagree the analysis is measuring a text the campaign never ran on.
- **`drift.py`** — the two halves.

**Survival is deterministic and asserted through the real `GMPromptBuilder`.** Reading the
ledger back would pass with the builder disconnected entirely, which is precisely the
silent failure D-002 exists to prevent, so the check renders the prompt a second session
*would send* and looks for each fact in it.

**Contradiction is judged on the batch seat**, per Fable's 08-14 endorsement of the P2.2
supersession deferral: measure the frequency before choosing a fix. Two guards, in the
tradition of the sweep's grounding check — the judge is only asked about facts that share
substance with the passage (the common case, a fact the passage never mentions, never
reaches it), and every claimed contradiction must **quote the passage verbatim**, checked
in code. A judge that cannot point at the text is not reporting a contradiction, it is
producing one.

### The measurement

Both archived play fixtures, which predate P2.2 and therefore carry **zero canon tags** —
nothing was being fed back to the GM, so this is the rate for a GM working unaided. That
is what makes them the before-picture rather than a problem.

| | turns | facts recovered | survived | lost | checks | contradictions |
|---|---|---|---|---|---|---|
| Salt Road | 11 | 19 | 19 | 0 | 44 | 0 |
| Ashmill | 32 | 224 | 224 | 0 | 329 | 0 |
| **total** | **43** | **243** | **243** | **0** | **373** | **0** |

**Zero contradictions in 373 checks, and zero facts lost by the pipeline.**

### I did not trust that zero, so I tested the instrument

A judge that never says yes produces exactly this number. So: a positive control against
the real 70B — three passages that plainly contradict a standing fact, four that plainly
do not, including the four failure modes the prompt warns about.

**First run: 3/3 recall, 1/4 false positives.** The judge fires, quotes correctly, and the
one it got wrong was a character *claiming* something ("a carter tells you he crossed the
bridge last week") — over-reporting, not under-reporting, which makes a measured zero more
credible rather than less. I tightened that one bullet with the failing case as a worked
example: **3/3 recall, 0/4 false positives**, and re-ran the shorter fixture to confirm the
zero reproduces on a freshly recovered fact set. It does.

### What the zero means, and what it does not

It means **supersession does not need an inline path yet** — that is the evidence Fable's
deferral was waiting for, and the answer is "not on this data".

It does not mean the GM never drifts. Three honest limits: 43 turns is a small sample and
both sessions are short; the relevance pre-filter cannot catch a contradiction phrased in
entirely different words (dropped pairs are counted as `skipped`); and a single session is
the easy case — the interesting drift is *across* sessions, which needs two sessions of the
same campaign, which the archive does not yet contain.

### A live-run finding that was a real bug

The first `dndc drift` run returned zero facts from a three-turn session. The fixture was
**Sam building Brother Hammond** — P1.4 reuses `gm_narration` with `scene: "character
creation"` rather than adding an event family, and the P1.4 handoff called that field "an
adequate discriminator for Phase 7 filtering". This is that filtering, and replay was not
doing it. An interview about what a character should be like establishes nothing about the
world, and a drift measurement that counted it would be measuring the wrong conversation.
Fixed, with a second test for the subtler half: dropping the narration while keeping the
player's line would have attached "a big gentle fighter" to whatever scene came next.

### Known issues

- **The sweep recovers 7 facts per turn and is not reproducible run to run** — 224, 269
  and 19, 13, 12 facts from the same two logs across runs, at temperature 0.1. Fine for a
  survival check (everything recovered survives either way) but it means any *repeat* drift
  measurement compares different fact sets. If Phase 7 wants a stable baseline this needs
  either a fixed seed or a recovered-canon fixture checked into the repo. **FOR DESIGN:**
  non-blocking, and I would rather raise it now than have Phase 7 discover its baseline
  moves.
- The contradiction scan costs ~5 minutes for 32 turns on the 70B. Fine for an offline
  instrument, and worth remembering before anyone reaches for it in a loop.
- SRD backgrounds and class starting equipment still not ingested — **next task**, per
  Fable's scheduling directive.

### Recommended next task

**The backgrounds + starting-equipment ingest**, per the 2026-08-14 scheduling directive:
queued since 08-05, and combat is where weightless gear and skill-short sheets stop being
cosmetic. The SRD weight lookup pairs naturally with P2.4's 0.0-weight gap. Then Phase 3.

---

## 2026-08-14 (b) — Fable's 08-14 rulings applied: the seat split and proposal grouping (Claude Code, kelly-pc)

**Both CC-owned rulings implemented. 790 tests, suite still fully offline.** No TASKS.md
work this session: per the pickup protocol, newly ruled items outrank phase order, and two
of the 08-14 rulings were mine to build. P2.6 is still next.

The other rulings needed no code — the chronicle no-gate call was confirmed, the P2.4/P2.5
deviations approved, the P2.2 supersession deferral and the `input_tokens=2` non-fix
endorsed, and the backgrounds + starting-equipment ingest is now scheduled after P2.6.

### The utility seat split

`config.yaml` now has `utility_interactive` (llama3.1:8b — the sweep) and `utility_batch`
(llama3.3:70b — the chronicle and its fold). `build_utility_backend` became
`build_interactive_backend` / `build_batch_backend`.

**A pre-split config fails loudly with instructions rather than migrating.** Mapping the
old `utility:` onto both seats would have been two lines and would have put the 8B in the
batch seat — the config would read as upgraded while the chronicle stayed exactly as
wrong. A silent migration that defeats the ruling it implements is worse than an error
message.

**Both seats are named in the log.** `cost.seat` is now `utility_interactive` or
`utility_batch`, and `session_meta.seats` carries both. Neither is a D-008 vocabulary
change — `Cost.seat` is free text and the seats map is free-keyed, so this is data, as
Fable's ruling says models are. But it is the thing that makes the split measurable at
all: a log that cannot say which seat ran cannot answer the question the split was made
to answer.

### The live run that mattered: the 70B fixes the Brakewater inversion

Same session log, same prompt, same grounding — only the seat changed:

> **8B (08-14):** "…arrived at Brakewater landing **after crossing the river** in the late
> evening… Hammond **paid for his own crossing and stepped aboard**, leaving him stranded
> on the Brakewater landing with no way back."
>
> **70B (today):** "…arrived at Brakewater landing **on a ferry that immediately departed,
> leaving them stranded** for the night after the ferryman had been bribed to not make any
> more crossings… **After a failed attempt to pay the ferryman and return to the other
> side**, Corin and Brother Hammond were left with the oilcloth man… **they had yet to
> learn who had paid the ferryman off**."

The geometry is right, and it closes on the unresolved thread — the sentence the template
asks for and the 8B never once produced across six sessions. **79.9s against ~6s**, which
is the trade the ruling priced in and it is free on a job nobody waits for.

End to end through the CLI on a throwaway campaign: `session_meta` carries both seats,
the sweep logged `utility_interactive llama3.1:8b local`, the chronicle logged
`utility_batch llama3.3:70b local`, and the summary named the actual dispute and left it
open.

### Proposal grouping — and an honest note about it

`cluster()` in `sweep.py`, used only by the confirmation UI. Jaccard over content words
(≥4 characters) at **0.6**, with statements under three content words never grouped —
"the bridge is out" and "the bridge is fine" share their only long word and are opposites,
which is precisely the silent suppression the npc-village lesson warns about.

Display only, as ruled: every proposal is still printed, still offered, and still logged.
Choosing a group files its first phrasing and **declines the others, logged as declines**.
That keeps the raw proposal count honest at the cost of the sweep looking less precise
than it is — *Phase 7 should cluster the `canon_write` rows before computing sweep
precision, since it has the text.*

**It did not visibly fire in tonight's live run**, and I would rather say so than imply
the flood is fixed. Sixteen proposals from a one-turn session, all sixteen distinct
enough to stay separate — including a pair about the same dog and treeline that a looser
threshold would have merged and that are, read closely, complementary rather than
duplicate. The tuning is pinned by tests against the verbatim 08-13 strings (the four
barking-dog restatements, the two rail restatements), where it does group. Conservative
was the instruction and conservative is what this is; if the flood recurs at this
threshold, the fix is to revisit the number with new evidence, not to loosen it now.

### Known issues

- **The sweep's volume is unchanged** — sixteen proposals for a single exchange. Grouping
  addresses redundancy, not volume, and the ruling scoped it to redundancy. Whether a
  one-turn session yielding sixteen "facts" is a prompt problem rather than a display
  problem is a real question, and P2.6 will produce the data to answer it.
- SRD backgrounds and class starting equipment still not ingested — now formally the task
  after P2.6, per Fable's scheduling directive.

### Recommended next task

**P2.6** — the drift test, closing Phase 2. Replay the archived Ashmill and Salt Road logs
from `\\TRUENAS\shared\data\dnd-campaign-logs\`, extract canon, and assert the established
world survives into a second session. It now also carries the measurement Fable asked for
in endorsing the P2.2 deferral: **live-contradiction frequency**, which decides whether
supersession needs an inline path at all. Then the backgrounds + equipment ingest, then
Phase 3.

---

## 2026-08-14 — P2.5: the chronicle, and the prompt stops growing (Claude Code, kelly-pc)

**P2.5 done. 776 tests, suite still fully offline.** No open decisions waiting. The
utility-seat `FOR DESIGN:` from 08-12 is still open and still non-blocking; `config.yaml`
seats are untouched, and there are numbers for it below.

D-002's third layer. The ledger can tell the GM that the mill burned down and who keeps
the waystation; it cannot tell it that the party spent an evening failing to get a
straight answer out of her. At session end the utility tier writes the session up as one
paragraph, and that paragraph is in every later session's prompt.

### No confirmation gate, unlike the sweep — and why

**FOR DESIGN:** *(non-blocking; the work is reversible in about ten lines if Fable
disagrees.)* The P2.3 sweep is table-confirmed because its output enters the canon ledger,
which is the instrument this project measures drift with. I did **not** gate the
chronicle, on three grounds:

1. **It is not canon and structurally cannot become canon.** D-008 keeps `chronicle_write`
   a separate event family for exactly this reason — a lossy summary must not be able to
   enter the ledger as a fact — and nothing in the code path can file one.
2. **It is regenerable and hand-editable.** `chronicle.yaml` is data. A wrong entry is
   deleted or rewritten; a wrong canon entry has already been counted as ground truth.
3. **Asking the table to approve a paragraph of prose at 11pm buys little and costs the
   thing that makes it usable**, which is that it happens by itself. Six one-line facts
   are reviewable at the end of an evening. A paragraph is not, and "yes" would become
   reflexive within two sessions — which is a gate in name only.

Instead it is *printed* at session end so a bad one is seen, and it is **subordinated in
the prompt**: the section is labelled "recollection, not record", and where it disagrees
with canon, canon wins. That is the ratified contradiction rule applied to the layer most
likely to be wrong.

### The grounding check moved, and now guards both jobs

`memory/grounding.py` — extracted verbatim from the sweep, no behaviour change beyond one
correction noted below. The chronicle needs it for the same live reason the sweep did: a
small model handed a tight prompt will answer with names from somewhere other than the
text. A summary that names someone the session never mentioned is **retried once with the
offending names quoted back at it, then skipped**. No chronicle entry is strictly better
than a fabricated one — the ledger still has the facts, the window still has the last
turns, and it regenerates for free next session.

One deliberate correction while extracting: the name check is now sentence-aware, so a
capitalised word opening the *second* sentence is no longer treated as a name. The old
version only skipped the first word of the whole statement, which was right for the
sweep's one-sentence facts and wrong for a paragraph. This slightly loosens the sweep for
multi-sentence proposals; the alternative was two copies of one rule, drifting.

`_transcript` also moved out of `sweep.py` to `gm/context.py` as `render_transcript` —
both memory jobs read a session back, and neither should have to import the other.

### The fold, which is the part that makes it a compression job

Without it the chronicle is a growing transcript in slow motion, and D-002's prompt rule
quietly stops being true around session twelve. Past eight entries the oldest four are
compressed into one entry covering all their sessions (`chronicle_write.covers_sessions`
is a tuple for exactly this). The originals are **dropped**, not kept the way superseded
canon is — superseded canon is the record of what used to be true and is what drift is
measured against, whereas a pre-fold summary is just a longer version of the text
replacing it, and the session log still has every word.

A failed fold is not a failed session: tonight's entry is already filed, and the next
session tries again.

### Live runs — six sessions on the real seat, plus one end to end

Standalone over archived logs, `llama3.1:8b` at temperature 0.2:

- Six sessions summarised, **`ungrounded`/`invented` empty on every one**, 1.6–6.2s each.
- Entries run **690–1,120 characters (~170–280 tokens)**. Eight of them before the fold is
  ~1,800 tokens added to the volatile half of every prompt. Real, and roughly two orders
  of magnitude cheaper than the transcript it replaces.
- **The fold fired live**: five sessions in, three entries out, the fold covering the
  oldest three, grounded.

End to end with the real GM seat: a two-turn `api` session wrote `chronicle.yaml`, logged
one `chronicle_write` (`covers=('20260814-184923',)`, ~281 tokens) and two free `local`
cost rows, and `dndc gm --campaign … --show-prompt` shows the paragraph in the next
session's prompt under "The story so far".

### One prompt fix the live runs forced

The first pass reported *options* as events — "Corin could have pressed him about the
boy" turned into narrative. The GM ends turns by naming things the party could do (D-006
scaffolding), and to a small model reading the transcript those look like beats. The
template now says explicitly that an offered option is not an event, and the leak stopped.

### Known issues

- **The 8B inverts relationships it has the facts for.** In the end-to-end run it wrote
  that the party "arrived at Brakewater landing after crossing the river" when they were
  at Brakewater and the ferry left without them, and called Hammond stranded on the wrong
  bank. Every name and object is real; the geometry is wrong. Grounding cannot catch this
  — it is a comprehension failure, not a fabrication — and it is the strongest evidence
  yet for the seat question already flagged: a batch job nobody waits on has no reason to
  run on the fastest model. See the numbers under the `FOR DESIGN:` from 08-12.
- The chronicle is not yet consumed by anything except the GM prompt. A `/chronicle`
  command to read it during play would be the obvious small addition; not built, not
  needed yet.
- The sweep's near-duplicate flood (noted 08-13) is unchanged.
- SRD backgrounds and class starting equipment still not ingested (queued, non-blocking).

### Recommended next task

**P2.6** — the drift test, and the last task in Phase 2: replay the archived Ashmill and
Salt Road logs, extract canon, and assert the established world survives into a second
session. Fixtures are on the NAS at `\\TRUENAS\shared\data\dnd-campaign-logs\`, confirmed
present by Fable on 08-10. This is the task the whole phase was built to make possible,
and it is also where the two local-model quality findings above become measurements
rather than anecdotes.

---

## 2026-08-13 — P2.4: items are state (Claude Code, kelly-pc)

**P2.4 done. 741 tests, suite still fully offline.** No open decisions waiting; the only
live `FOR DESIGN:` is yesterday's non-blocking utility-seat question, which this task does
not touch (`config.yaml` seats unchanged) — though see the sweep note below, which is
fresh evidence for it.

This closes Finding 5 from the first playtest: the party finished that session carrying,
in the fiction, several things no sheet had ever heard of. Fable's 2026-08-05 ruling —
items are state, the GM proposes and the engine performs, wire format is CC's call,
doc-first per D-008.

### D-008 amended first

Two things written down before any code:

- **The tag.** `[[GAIN: <character> — <item> ×<quantity>]]` and `[[LOSE: ...]]`, both
  optional fields optional. **Two verbs rather than one tag with a direction field**,
  because a direction word is a thing a model can get subtly wrong, and a missing one
  would have to be guessed — which way an item moved is not a guessable field. Fifth use
  of the `[[TAG:]]` convention, and the `[[`-suppressing stream filter already hides it.
- **`inventory_change.applied`** — whether the sheet changed *as proposed*. `confirmed`
  is the humans agreeing; `applied` is the engine managing it. They come apart when the
  GM narrates losing something the sheet never held, which is Finding 5 exactly, and a
  row that cannot say so cannot be weighed. (Same argument as yesterday's `canon_write`
  fields; I am aware that is twice in two days, and both times the field existed to make
  a real divergence visible rather than to decorate a row.)

### The parser drops what it cannot read — the opposite of the canon parser

`canontag.py` bends over backwards never to lose a fact: an unrecognised leading word
becomes part of the statement rather than a bad scope, because a fact filed under the
wrong scope beats a fact on the floor. `inventorytag.py` does the reverse — no item name,
or a narrated clause where a name should be, and the tag is dropped.

The asymmetry is the point. A lost canon line costs the ledger a sentence. A misread item
change writes the model's fiction into a character sheet, which is the failure the task
exists to end. Same reasoning that makes `[[CHECK]]` refuse to guess a DC.

Surface form is still forgiving, because the producer is a language model: `×3`, `x3`,
`(3)`, `3 torches`, `three torches`, `a pair of boots`. Only an em/en dash or `--`
separates the character from the item — a single hyphen and a colon both live inside
ordinary item names ("half-empty waterskin"), and splitting on those would invent a
character out of half an item.

### Where each piece lives

- `gm/inventorytag.py` — parse and strip. No state.
- `rules/inventory.py` — pure functions over an inventory list, per the rules-core rule.
- `game/inventory.py` — `InventoryStore`: resolves who a tag meant, performs the change,
  writes the sheet back atomically **per change** (same argument as the canon ledger — a
  session that dies at turn 40 must not take the party's gear with it), logs the event.
- `game/turn.py` — collects proposals at the same choke point canon uses, and applies
  **nothing**. Confirmation is an interface act, so the engine only carries the proposal.
- `game/cli.py` — `confirm_inventory`, run per turn right after the canon lines.

`resolve_member` moved out of `cli.py` into a new `game/party.py`. Three callers now need
"who does this name mean" (`/switch`, `/inventory`, and the item store), and the live run
proved it: the GM wrote `[[LOSE: Corin — waterskin]]` for *Corin Vale*, and a second,
dumber matcher in the store would have had to be right about that independently.

### `/inventory` was not in the task, and the task is wrong without it

The prompt now tells the GM it does **not** know what the party is carrying — the sheets
are not in its context, so narrating someone using or running out of a specific item is
inventing state. That instruction is hollow if the players have no way to look. `/inventory
[name]` prints the pack from the sheet, which is OD-11's principle applied to gear:
authoritative state is displayed from state, and the model is never the one saying what
it is.

### Live run — all three outcomes, on the real GM seat

Two short `api` sessions, ~$0.05 total.

1. **confirmed + applied.** Traded a waterskin for a lantern; the GM tagged both sides of
   the trade unprompted. Both filed, sheet on disk updated, `/inventory` showed the new
   pack.
2. **confirmed + not applied.** Gave away the waterskin a second time — no longer on the
   sheet. Printed `loses waterskin — not on the sheet` in yellow and logged
   `applied: false`. That is Finding 5's divergence, now visible in one field.
3. **declined.** Refused the dagger in the same batch; logged `confirmed: false`, and the
   sheet still shows both daggers.

Also confirmed live: EOF at the prompt declines everything (the sweep's proposals at the
end of run 1 were all declined that way when stdin ran out), and the GM did *not* tag a
gain for the NPC receiving the items — only player characters have sheets.

### Known issues

- **The P2.3 sweep proposed 22 facts for a 3-exchange session, with heavy near-duplication**
  — the same barking dog four times in different words, the same wobbling rail twice, the
  same cold draught three times. Grounding is doing its job (all 22 were real), but
  `llama3.1:8b` restates itself within a single chunk and the store only suppresses exact
  ledger matches. This is not a P2.4 regression and I did not fix it inside a P2.4
  session, but it is worth reading next to yesterday's measurement (the 70B gave 3 clean
  facts on a longer transcript) as evidence on the seat question already flagged.
- Weight for a gained item is **0.0** — this module has no SRD repository, and inventing a
  plausible weight would put a fabricated number into carried weight. So encumbrance is
  understated for anything picked up in play until the SRD equipment table is wired in
  (that lookup is a natural pairing with the queued starting-equipment ingest).
- SRD backgrounds and class starting equipment still not ingested (queued, non-blocking).

### Recommended next task

**P2.5** — the chronicle layer: a compression job on the utility tier writing
`chronicle_write` events, and a prompt builder that consumes ledger + chronicle + window.
This is where the utility-seat question stops being hypothetical (a 180s batch job nobody
watches has the opposite latency/quality tradeoff to the sweep), so a ruling on that
`FOR DESIGN:` before or during P2.5 would be useful — but P2.5 is not blocked on it, and
the default is to keep one seat.

---

## 2026-08-12 — P2.3: the end-of-session sweep (Claude Code, kelly-pc)

**P2.3 done. 685 tests, suite still fully offline.** No open decisions were waiting, and
no `FOR DESIGN:` tags were blocking, so this is straight TASKS.md order.

The premise, from the 2026-08-10 entry: *"the opening scene tagged nothing at all, and the
second turn established several concrete facts … and tagged none of them."* Inline
extraction gets what the GM remembers to declare, which is not everything it establishes.
The sweep is the backstop — at session end, the utility tier reads the session's turns and
proposes the durable facts nobody wrote down.

### D-008 amended first, per its own rule

The sweep gives the canon ledger a **second writer**, on a different model tier and at a
different level of trust. A row that cannot say who wrote it cannot be weighed, so
`canon_write` gained two fields:

- **`source`** — `gm_tag` | `sweep` | `co_creation` | `authored`. Without it, "how much of
  this ledger was written by a local 8B?" is a string match on `established_by`.
- **`confirmed`** — as on `inventory_change`, and for the same reason. A proposal the
  table declined is logged with `confirmed: false` and **never enters the ledger**.

Doc first, then `schema/events.py`, then the writers.

### Four guards, all structural

In the OD-11/OD-12 tradition — protection by construction, not by instruction. The prompt
asks nicely; the code is what actually holds.

1. **Scope is forced to `player_known` in code.** The sweep cannot file a secret. Whatever
   scope the model claims is discarded, not honoured.
2. **`gm_only` canon is never sent to the local model.** Its proposals get printed to the
   table, so anything it reads is one echo away from the players' screen.
3. **Every proposal is grounded against its own transcript chunk** — see the hallucination
   finding below.
4. **The table confirms.** GM-tagged canon auto-files (the GM is the authority and the tag
   is deliberate); an 8B *inferring* that a fact was established has a real false-positive
   rate, and unreviewed local-model facts entering the ledger would be drift we injected
   into the instrument we use to measure drift. Batch confirm costs one keystroke.

The sweep reuses the GM's `[[CANON: ...]]` format, so `find_canon_tags` is the single
parser: preamble from a chatty small model is ignored structurally, and there is one place
to fix a parsing bug.

### Three live-run findings, all of which changed the code

Per the live-run rule — a task with a model-facing surface is not done without one.

**Run 1 — play-by-play.** 25 proposals from 11 turns, mostly scene ("The guard notices
Corin crouched by the wagons"), player actions, and weather. The prompt was rewritten
around one durability test — *if the party leaves and comes back in three sessions' time,
will this still be true?* — with an explicit non-facts list and a `{{ party }}` block so
the model knows whose actions are never the world's.

**Run 2 — the model recited my examples.** The 8B answered with the prompt's own three
worked examples verbatim, naming an NPC who appears nowhere in the transcript. Fixed
twice over: the examples moved to an unmistakably different setting with "these are
illustrations only — writing any of them down would be an error", **and** a deterministic
`_grounded()` check landed, because prose cannot stop that and it *was* prose that caused
it. The check requires every non-sentence-initial capitalised word to appear in the
transcript, plus ≥50% content-word overlap; it strips the possessive (`Ashmill's` →
`Ashmill`) and nothing else. Deliberately no further stemming: a matcher clever enough to
equate "burned" with "burning" is also clever enough to accept an invention. Ungrounded
proposals are dropped and counted in the report.

**Run 3 — the sweep answered NONE** (2 output tokens) on a log that gave 23 proposals when
swept standalone minutes earlier. Two causes: the prompt said NONE was "a good answer you
should expect to give often" (softened), and **the local seat was running at Ollama's
default temperature**, so the same input gave "23 facts" and "none" on consecutive reads —
not a measurement of anything. `OllamaBackend` now takes an optional `temperature`, and
the sweep pins `SWEEP_TEMPERATURE = 0.1`. Three repeat sweeps after the fix agreed on 5–6
facts with `ungrounded=0`.

### 8B vs 70B on the same fixture — a config choice, not a code change

Same 11-turn Salt Road log, same prompt: `llama3.1:8b` gave **10 grounded proposals in
~3.7s**; `llama3.3:70b` gave **3 clean durable facts in ~180s**. The 70B is visibly more
selective; the 8B trades precision for recall, which the confirmation gate absorbs.

I did **not** change `config.yaml`. The utility seat is also P2.5's compression seat, where
the tradeoff runs the other way (a lossy summary nobody confirms wants the better model,
and 180s at session end is fine), and the model is data. So this is a one-line choice for
Kelly with the numbers recorded rather than a decision I made quietly.

**FOR DESIGN:** *(non-blocking — P2.5 raises it for real, I am flagging it early.)* Should
the utility seat be **split** — a fast small model for interactive jobs the table waits on
(the sweep, at 3.7s) and a bigger one for batch jobs nobody watches (chronicle
compression, at 180s)? Today one seat serves both, and the numbers above say the right
answer differs per job. This does not block P2.4.

### End-to-end verification

A live play session on a throwaway campaign, GM seat included: 6 proposals surfaced, answer
`1 2`, "2 filed" with `canon:` lines and "4 declined (logged, not filed)". The log carries
one `utility llama3.1:8b local 1347/174 $0.0` cost row, two `source=sweep confirmed=True`
rows and four `confirmed=False` rows; `canon.yaml` holds exactly the two accepted facts,
stamped with the session id. Throwaway campaign deleted, as with the P2.1 one.

### Deviations and notes

- **`OllamaBackend` gained a `temperature` argument** — not in P2.3's scope as written, but
  a sweep that answers differently on identical input is not testable, and this is the
  smallest fix that makes it so. `options` is only sent when the temperature is set, so
  every existing caller is byte-identical on the wire.
- **`parse_selection` returns `None` for unreadable input** rather than an empty set, so
  "" and "wat" are not both silently treated as "decline everything". Three attempts,
  then decline; EOF/Ctrl-C declines.
- The sweep chunks at 8 turns and caps at 40 proposals; later chunks are told what earlier
  chunks found, so the model does not re-propose within a session. Grounding is per-chunk,
  not per-session — a fact must be grounded in the text it came from.
- A failed sweep (backend unreachable, or any unexpected error) writes nothing and reports
  the error. Session end never fails because the local box is down.

### Known issues

- The sweep proposes nothing about **items** — inventory is P2.4's `[[GAIN/LOSE]]` path,
  and deliberately not something the sweep infers.
- SRD backgrounds and class starting equipment still not ingested (queued, non-blocking).

### Recommended next task

**P2.4** — `[[GAIN: ...]]` / `[[LOSE: ...]]` → `inventory_change` events, engine mutates
the sheet, player/CLI confirmation, rejected proposals logged. The confirmation UI built
here (`parse_selection` / `choose_proposals`) is the obvious thing to reuse.

---

## 2026-08-10 — P2.1 + P2.2: canon persists, and the GM writes it (Claude Code, kelly-pc)

**P2.1 and P2.2 done. 640 tests, suite still fully offline.** Fable's 2026-08-10 rulings
were applied before any new code, per protocol — the contradiction rule is now built as
ratified rather than as my proposal, and the `FOR DESIGN:` tag on it is retired.

Also, at Kelly's request: **`config.yaml` billing default is back to `api`.** That happens
to be what OD-16 implies anyway — campaign cost claims come from `api` runs only, so the
default play path should be the one that produces usable measurements.

### The `input_tokens = 2` "capture hole" is not a bug — no fix was written

OD-16 approved this fix; I am reporting that there is nothing to fix, with the evidence,
rather than writing a change that would have made the numbers worse.

Two live `claude -p --output-format json` probes on kelly-pc today. In a **two-turn**
invocation, the top-level `usage` block reported 16/128/47,033/16,820 — matching
`modelUsage` and `total_cost_usd` exactly — while `usage.iterations` carried **one entry
for two turns** (6/8/25,673/6,210). So the top-level block *is* the correct aggregate, the
adapter already reads it, and the obvious "fix" (summing `iterations`) would have
under-reported by about 60%.

The `2` is a true measurement. Confirmed against the archived Salt Road logs: every
subscription cost row reads `input_tokens: 2` with 8.7k–11k `cache_write` — the prompt is
cache-*written* every turn, so there is almost no uncached input left to count. That is
the per-turn rewrite OD-16 already ruled inherent to headless CC and outside our boundary.
Pinned by `test_subscription_usage_reads_the_aggregate_not_the_iteration_list`, which
carries the real captured payload so the next person to read `iterations` and think it
looks more precise has a test explaining why it is not.

*(Method note: the first probe ran with `ANTHROPIC_API_KEY` live in the shell and so
billed the key ~$0.015 rather than the pool — the exact trap `subscription.py` exists to
avoid, met in person. The second stripped both metered vars, which live-verified
`child_env()` at the same time.)*

### P2.1 — `CanonStore` (`src/dndc/memory/canon_store.py`)

The ledger, its file, and the log are three things every canon write has to touch, so one
object owns all three. Every write persists immediately and atomically (temp file, then
`os.replace`): a session that dies at turn 40 must not lose forty turns of world, and a
crash *during* a save must not leave half a ledger where a whole one was. Cost is a small
YAML rewrite per new fact, which is nothing beside the model call that produced it.

Three outcomes when the GM declares something — `establish`, silent suppression if the
ledger already holds it, and `note_conflict`. Restatement suppression matters more than it
looks: the GM names the town every other turn, and a ledger that grows a row each time is
not a ledger. It is suppressed in the *log* too, or Phase 7 counts restatements as
establishment and every campaign scores as maximally generative.

### P2.2 — inline `[[CANON: ...]]` (`src/dndc/gm/canontag.py`)

    [[CANON: <scope> (<subject>) — <the fact>]]

Scope and subject optional; `[[CANON: The bridge is out.]]` is a well-formed world fact.
The parser's rule is that **it must never lose a fact to a formatting slip** — an
unrecognised leading word becomes part of the statement rather than a rejected scope. That
is the opposite of `[[CHECK]]`'s posture and deliberately so: a missing DC means the GM
never made the ruling, so guessing invents the adjudication the log exists to audit, while
here the fallback *is* the common case. Scope alternatives are generated from the
`CanonScope` enum, so a new scope cannot be parseable in one place and unknown in another.

Extraction happens in `turn.py::_call` — the one place every GM call passes through,
including the second narration call of a turn that asked for a check. Two call sites would
each have been correct on the day they were written and one of them wrong later.

Two guards worth naming:

1. **The engine rebinds `campaign.ledger` to the store's ledger.** A store over a
   *different* ledger object would file facts to disk that never reach the prompt —
   durable, invisible, and unnoticeable in play. Now it cannot be wired wrong from outside.
2. **`gm_only` facts are never displayed, not even counted.** The CLI shows the table what
   the world just committed to; a line reading "1 fact recorded (hidden)" tells the players
   a secret was written, which is a smaller leak of the same kind. Test pins it.

### Live run (protocol: a model-facing surface is not done without one)

Throwaway campaign, `api`, two turns, since the prompt template changed. The GM tagged two
facts on its first player turn, both parsed with the right scope, both written to
`campaigns/<slug>/canon.yaml` with session and turn provenance, both logged as `create`,
neither tag visible in the prose. A second `TurnEngine` built cold from that directory
carried "Halda Orrin" into its prompt — the Phase 1 known issue, closed.

**Finding, and it is the argument for P2.3:** the opening scene tagged nothing at all, and
the second turn established several concrete facts (lay brothers through four or five days
ago, a peddler two weeks back, the road otherwise quiet) and tagged none of them. Inline
extraction gets what the GM remembers to declare, which is not everything it establishes.
The end-of-session utility-tier sweep is not a nice-to-have; it is the half that catches
what the GM does not think to write down. Free and local, so there is no reason to skip it.

### Deliberate deferral: no inline supersession

The GM cannot supersede an entry from a tag, only create. Superseding needs the target's
id, which would mean rendering ids into the prompt — tokens on every turn, and an
invitation to retcon by tag, which is close to the "narration wins" model Fable explicitly
rejected. `CanonStore.supersede()` exists and is tested; nothing in the turn loop calls it.

The cost is real and I would rather state it than bury it: if the world genuinely changes
(the bridge collapses), the ledger will hold both "the bridge stands" and "the bridge is
out" as live facts, and the prompt will carry the contradiction. **P2.6's drift test should
measure how often that happens** before we decide the fix — a `/canon supersede` table
command, a sweep-driven proposal, or something else. Choosing now would be guessing.

**FOR DESIGN:** none blocking. The deferral above is a scoping call, not a rule change,
and it is reversible; flagging it only so Fable sees it named rather than discovering it in
P2.6's numbers.

### Recommended next task

**P2.3** — the end-of-session backstop sweep on the utility tier. The live run above is the
case for it, and it needs no ruling.

### Known issues / notes

- Turn provenance counts the opening scene as turn 1, so a player's first turn records as
  `turn: 2`. Consistent with `campaign.history` indexing; noting it so nobody reads it as
  an off-by-one.
- Backgrounds and starting equipment still not ingested (unchanged, queued).
- `dndc play --canon PATH` loads a ledger but does not adopt it: canon established in that
  session is logged and held in memory, never written back to the file passed in. Writing
  to a file handed over for inspection would be a surprise.

---

## 2026-08-09 (b) — Phase 2 started: D-008 vocabulary + ledger machinery (Claude Code, kelly-pc)

Same day, after the Phase 1 close below. **P2.1 partially done**; 599 tests.

TASKS.md now breaks Phase 2 into **P2.1–P2.6**. The one architectural choice made here is
**how canon gets extracted**, and it was between three options: a second model call per
turn (~2× per-turn cost), an end-of-session pass only (canon absent during the session
that established it), or **the GM emitting `[[CANON: ...]]` inline as it narrates**.

Chose inline, with the end-of-session sweep kept as a backstop on the utility tier (free,
local). It is the fourth use of the tag convention `[[CHECK]]` established, the
`[[`-suppressing stream filter already hides it from players, and it makes the GM's
commitment explicit at the moment it makes it. The one failure mode — the GM forgetting to
tag — is exactly what the backstop sweep covers.

### D-008 amended (doc-first, per D-008's own rule), then the schema

1. `canon_write.scope` documented as the `CanonScope` enum. The old comment named
   `world_truth`, `quest_state`, `pc_fact` — none ever written by code. This is the
   correction Fable queued at the P1.4 handoff for "the next D-008 touch".
2. `canon_write.operation` gains **`conflict`**: narration contradicted an existing entry
   and *the entry was kept*.
3. **`inventory_change`** — the 08-05 ruling that items are state. GM proposes, engine
   performs. A declined proposal is logged with `confirmed: false`.
4. **`chronicle_write`** — separate family from `canon_write`, so a lossy summary cannot
   enter the ledger as an established fact.

The vocabulary is pinned by a test that had to be updated to add a family. That is the
intended friction, and it worked as designed.

### Ledger machinery (P2.1)

`supersede()` keeps the old entry on file with a `superseded_by` pointer and drops it from
`for_gm()` / `scoped()`; superseding twice is an error, because two live replacements for
one fact means the ledger has forked. `mint_id()` derives readable ids from the fact text
so the same fact tends to land on the same id across runs — which is what makes a replay
diff mean anything.

**Supersession and conflict are deliberately different paths.** Supersession is the world
changing (the reeve died). Conflict is the model contradicting itself (the reeve is
suddenly called something else), and there the entry is kept and the conflict logged. A
ledger that silently follows the latest narration cannot measure drift, because it has
agreed with the drift by definition.

**FOR DESIGN:** the contradiction rule above is my call, not a ruling — flagged for the
Phase 2 batch. If Fable wants new narration to win, or wants the GM asked to arbitrate,
that changes P2.2. Building to canon-wins meanwhile; it is the conservative direction and
the reversible one. *(Resolved: ratified as canon-wins, 2026-08-10. GM-arbitration
explicitly rejected.)*

### Still to do in Phase 2

P2.1's remaining half (ledger persistence into the campaign directory during play), then
P2.2 inline extraction, P2.3 backstop sweep, P2.4 `[[GAIN/LOSE]]`, P2.5 chronicle, P2.6
drift test against the archived logs.

---

## 2026-08-09 — the two-player session, `/switch`, and OD-15 (Claude Code, kelly-pc)

**Phase 1 is complete.** Kelly and Sam played the first two-player session on 2026-08-07
(*The Salt Road*, 8 player turns, 4 checks, 70 minutes) — that session had no write-up and
no handoff entry, so this one covers it, plus the bug it exposed and the OD-15 ruling that
was sitting unimplemented. **589 tests passing** (27 new), still offline.

Write-up: `docs/playtests/2026-08-07-two-player-session.md`.

### The session

Sam built **Brother Hammond** in three exchanges from "let's think a little more
ridiculous" — an ex-doomsday-cultist fighter sworn never to lie, four canon facts. Play
opened on a caravan standoff; Kelly cased the wagons, got a canvas flap open, tried to
grift her way out of being caught, failed twice, and Sam walked Hammond over to stand
beside her as the session ended.

Hot-seat rotation — the last untested part of Phase 1 — works. The GM held two characters
without confusion and wrote Hammond *arriving* rather than restaging the scene.

### `/switch` was unusable, and the reason is the interesting part

`/switch corin` was rejected; the lookup wanted the exact full name. The rule was written
out **twice** — once in `_play_command` to decide the error message, once in the loop to
decide the switch — so the two could disagree about the same input.

Now one `resolve_member()`, matching in tiers (full name → a single name out of it →
prefix), stopping at the first tier that hits so a unique first name is never made
ambiguous by a longer name it prefixes. Player names match too. Ambiguity is reported
rather than guessed. Both call sites read it; the loop acts on a `CommandResult` instead
of re-parsing the command text it just handed over.

### OD-15 implemented

Ruled 2026-08-05, still listed under "Open now" at the head of this file — the pickup
protocol caught it before TASKS.md order did, which is what the protocol is for.

- `/scaffolding high|low|off` mid-session, via a new `GMPromptBuilder.set_scaffolding()`.
  Costs one cache miss when used, which is the right price for a setting touched once a
  session.
- The CLI hints the command exists every 12 player turns, and never at `off` where there
  is nothing left to turn down. A test asserts **no prompt template mentions
  `/scaffolding`** — if the GM knew about it, it would eventually offer it in prose, and
  OD-11 puts the interface in the chrome.
- Phrasing-variety clauses added to the `high` and `low` templates, naming the 23-of-32
  failure directly. `off` has no menu, so it has no closing sentence to vary.

**No D-008 change was needed.** `gm_narration` already carries a `scaffolding` field, so a
mid-session change is recorded per turn and Phase 7 can reconstruct the level at any point
without a new event type. Verified in a live run: `session_meta` says `high`, turn 6 says
`low`.

### Live run (protocol: a model-facing surface is not done without one)

Piped a scripted session through `dndc play`: `/who`, `/switch corin`, `/scaffolding`,
`/scaffolding low`, one turn, `/quit`. Switch handed over on the first name, the level
changed, the log recorded it. Two observations, both n=1:

- The first reply after dropping to `low` still offered three options. The window in front
  of it contained its own `high` opening, and it imitated itself. Watch whether the level
  takes hold a turn or two later; do not act on one turn.
- Both opening scenes generated this session closed with "or something else entirely" —
  the variety clause is not obviously biting on openings yet.

### Deviations

1. **`_play_command` returns a `CommandResult`** rather than `"quit" | None`. The old
   signature could not express "the active player changed", which is why that logic was
   duplicated in the loop.
2. **`/switch` matches player names as well as character names.** Beyond the ruling, but
   "Sam's turn" is as natural as "Corin's turn" at a two-person table.

### Known issues / notes

- `config.yaml` billing default is now `subscription`, set by Kelly during the 08-07
  session. Committed as-is — it is a real preference, not a test artifact.
- `input_tokens` reads `2` on every subscription-mode cost row. The usage capture in that
  adapter is broken, and it hid finding 5 until the log was summed.
- Backgrounds and starting equipment still not ingested (unchanged, queued).
- Fable's pre-authorised DC ladder is **not** recommended — DCs came out 12/12/13/14 this
  session, priced situationally. Anchoring was an n=3 artifact.

### Recommended next task

**Phase 2 — canon ledger + memory.** Two campaigns have now demonstrated the same hole
from opposite ends: the co-creation backstory drives every scene, and nothing written
during play survives the process. Two logged sessions exist as drift fixtures (Ashmill,
the Salt Road waystation).

Both are on the NAS and hash-verified, so Phase 2 can start cold:
`\\TRUENAS\shared\data\dnd-campaign-logs\` holds `20260805-063755.jsonl` (Ashmill,
archived by Kelly 08-06) and both Salt Road logs (archived 08-09). `logs/` is gitignored;
those copies are the retention.

**FOR DESIGN:** one, non-blocking — **OD-16**, promoted to the Open block above:
`would_have_cost` in subscription mode measures headless CC's harness overhead, not the
campaign, and OD-10's cost band reads it as the campaign.

---

## 2026-08-05 — first playtest, grant bugs, opening scene (Claude Code, kelly-pc)

**Kelly played the first real session** (solo, 1h21m, 29 turns, 3 checks, **$0.4961**).
Write-up: `docs/playtests/2026-08-05-first-play-session.md`. This entry covers that, plus
Fable's creation-review bugs, which are now fixed. 562 tests passing (50 new), still
offline.

### The playtest

It worked — Corin walked into Ashmill, drank at the Grey Hollow, eavesdropped on two
locals, lifted a coil of rope off a junk merchant, and searched a chapel out past
Vennhollow. Prose and pacing held for 29 turns, the co-creation backstory paid off in the
*first paragraph*, all content was original, and **OD-11 held completely**: zero engine
numbers in prose across 32 replies, with a failed Perception narrated as "whatever put it
here has kept its secret".

Findings, in order of how much they matter:

1. **The world is not remembered, and it is now demonstrable.** A town, two villages, a
   reeve, a sealed chapel and a bloodstained altar — none of it in the ledger, because
   play never writes canon. Re-running immediately afterwards, the GM opened in a city
   called *Kellmoor*; Ashmill no longer exists. Phase 2's justification, with an artifact.
2. **Scaffolding has become a formula.** 23 of 32 replies end with the literal sentence
   "— or anything else you'd like to try." Nothing implements D-006 fading, and the `high`
   template's phrasing never varies. Kelly repeatedly ignored the offered options and
   improvised instead, which is the readiness signal D-006 describes.
3. **Every DC was 12.** Three checks of visibly different difficulty, all priced the same.
   n=3, so this is a watch-item rather than an action, but `gm_adjudication` exists so
   Phase 7 can audit ruling fairness and an anchored GM makes that vacuous.
4. **The GM did not open the scene.** Kelly had to prompt the campaign into existence.
   Fixed — `TurnEngine.open_scene()` runs a GM turn before the first prompt when a
   campaign has no history, with an `opening.md` asking for a world already in motion.
5. **Picked-up items never reach the sheet.** A stolen rope, a silver ring and a knife;
   inventory unchanged. Fiction and sheet have already diverged, which is the same class
   of desync D-001 exists to prevent. Phase 3 will make it acute.
6. **Cost confirmed:** $0.0155/turn, ~$1.10 for a three-hour session. Inside OD-10's band.

### Fable's creation-review bugs — all four fixed

The review found that every omission was **a choice-point inside a species/class grant**:
fixed grants landed, grants requiring a choice were silently dropped. Fixed as ruled —
the data now carries the choices, `Concept` carries the answers, and `build.py` **raises**
rather than emitting a short sheet:

- `Species.ability_bonus_options` (Half-Elf's floating +1s) and `language_options` are
  ingested; `ClassLevel.expertise_choices` reads the Rogue's expertise out of the
  Features file, where it was nested as a choose-1-of-[choose-2-of-…].
- `SRDData.proficiency_types` ingests the SRD's own proficiency categories. The old code
  guessed from names with a keyword list, which is exactly why `thieves-tools` went
  missing — it contains none of the words a tools list would look for.
- `Proficiencies.tools` is now levelled like skills, because 5e expertise applies to
  tools ("one skill and thieves' tools") and a plain list could not say that. Old sheets
  still load — a `before` validator accepts the list form.
- `dndc sheet validate` now reports incomplete grants (a warning, not a failure: sheets
  are hand-editable data; construction is where incompleteness is fatal). Corin's
  hand-edited sheet passes clean.
- Test sweep over 5 species × 4 classes asserting no combination can silently skip a
  required choice, which is the general form of all four bugs.

### The interview would not converge

Three live runs in a row, the GM asked another round of questions instead of proposing —
including after the prompt was strengthened twice, once to a hard "your second reply must
contain a proposal". So the engine now says it instead: from the player's second turn,
until a character exists, a bracketed engine instruction rides along with the player's
message. Converged on the second reply immediately.

This is OD-12's principle in a third place. A rule the model must remember eventually
fails; a rule carried by what enters the prompt cannot. Worth noting the pattern is now
general enough to reach for first rather than after two prompt revisions.

### Deviations

1. **`Proficiencies.tools` changed shape** (list → dict of name to proficiency). A schema
   change, made because Fable's review named tool expertise explicitly and the old shape
   could not represent it. Backward compatible on read.
2. **`sheet validate` warns rather than fails** on incomplete grants. Construction raises;
   inspection reports. A hand-edited sheet mid-edit is not an error.
3. **The engine nudge is injected into the player's message**, not the system prompt —
   it is turn-scoped, and the system half carries the cache breakpoint.

### Known issues / notes

- Backgrounds are still not ingested, though `5e-SRD-Backgrounds.json` **is** in the
  pinned raw data — this is an ingest omission, not missing data. Charlatan would grant
  Deception + Sleight of Hand, and the class-skill picker will need to avoid
  double-granting when it lands.
- Starting equipment still comes through empty from ingest.
- Corin Vale's sheet was hand-edited by Kelly per the review and now validates clean.
- Findings 2, 3 and 5 above are untouched.

### Recommended next task

**P1.5 proper — a two-player session.** Sam still has no character, so `/switch` and the
hot-seat rotation remain the only untested part of Phase 1.

Then **Phase 2**, where finding 1 gets fixed. The playtest log is the test fixture: replay
it, extract canon, and assert Ashmill survives into a second session.

**FOR DESIGN:** one, non-blocking. **D-006 fading has no trigger.** The design says
scaffolding fades as players find their feet; nothing implements the fade, and finding 2
shows `high` wearing out inside one session. Player-initiated (`/scaffolding low`),
turn-count, or a GM judgment call are all plausible. My instinct is player-initiated plus
a nudge from the GM after N turns of the player ignoring the offered options, since that
is the actual signal — and separately, the `high` template should vary its closing
sentence even before any fade. One command would do for now.

---

## 2026-08-05 — `.env` was never loaded (Claude Code, kelly-pc)

**Follow-up fix, found by Kelly asking where to run `dndc` from.** Nothing in the
codebase read `.env`. `.env.example` documents it, D-004 specifies it, and the `api`
adapter's own error says *"no ANTHROPIC_API_KEY. Put it in .env"* — but no loader
existed, so the only way to run the `api` adapter was to already have the key exported.
Every live run in P1.1–P1.4 worked only because the key happened to be in the session
environment, which is exactly why four tasks of live testing never caught it.

`config.load_env_file()` now reads it, called from `cli.main()` before anything wants a
key. Hand-written rather than adding `python-dotenv` — the format is `KEY=value` and this
is a dozen lines. Two properties worth keeping: it resolves against the **repo root, not
the working directory**, so `dndc` runs from anywhere; and a real environment variable
always wins, so an exported key is never silently replaced by a stale file. D-004's
credential isolation is unaffected — the subscription adapter filters `os.environ`, so a
key injected from `.env` is still stripped from the child.

507 tests (5 new). Verified from a foreign working directory with the variable unset.

---

## 2026-08-05 — P1.4 guided character co-creation (Claude Code, kelly-pc)

**Completed: P1.4.** 502 tests passing (91 new), suite still fully offline. Verified live
three times end to end; the third run produced a playable bard, saved her, and then played
her through `dndc play --campaign` with no sheet flags. A full character costs roughly
$0.05.

This entry also carries Fable's OD-12 ruling edits to `DESIGN-DECISIONS.md` and the Open
block, which were sitting uncommitted in the worktree.

### What landed

- `rules/build.py` — `Concept` → validated level-1 `CharacterSheet`. Pure, deterministic,
  no model: allocation, species bonuses, HP, AC from an armour profile, class saves,
  skill legality, spell slots, spell-list validation.
- `gm/proposal.py` — `[[PROPOSE: ...]]` and `[[FACT: ...]]` parsing, same posture as
  `checkrequest.py`.
- `gm/prompts/creation_core.md` + `gm/creation.py` — the co-creation seat, with the SRD
  menu (species, classes, each class's skill list and count, armour) injected into the
  cached prefix so the GM cannot offer something that does not exist.
- `game/creation.py` — the interview loop, the repair path, and the write-out: sheet to
  `campaigns/<slug>/characters/`, backstory facts to `campaigns/<slug>/canon.yaml` as
  `character`-scope entries with `canon_write` events.
- `dndc create-character --campaign SLUG --player NAME`, plus `--show-prompt` as the
  offline inspector (the P1.2 pattern).
- `dndc play --campaign SLUG` / `dndc gm --campaign SLUG` load party and canon from disk.
  `--character` is now optional, which is what P1.4 was supposed to buy.

### The GM proposes an ordering, not numbers

This is the design decision of the task, and it is OD-12's governing principle applied to
allocation. The GM says `priority: cha, dex, con, wis, int, str` and the engine maps the
standard array onto that ranking. It never sees or states a score.

Three things follow. An illegal spread becomes **unrepresentable** rather than merely
rejected — a permutation of six abilities can only produce a legal array, so there is no
retry loop and no way for the model's point-buy arithmetic to be wrong. The judgment
actually being made is genuinely ordinal ("what does this character care about"), which is
OD-12's test for where the boundary belongs. And the player is never shown a number the GM
made up: the CLI renders the finished sheet, exactly as it renders check results.

Point buy works the same way — the GM picks a named shape (`focused` / `balanced` /
`even`), all of which cost exactly 27, re-validated through `assign_point_buy` because a
table nobody checks is a table that drifts.

### Three findings from running it live

1. **The GM interviewed forever and never proposed.** Three rounds of questions, no
   character. The prompt said "when the concept is clear enough" and gave it no reason to
   converge. It now says to propose within two or three exchanges and that a character on
   the table beats three more questions — build early, change later.
2. **It named the character after the player.** Asked to build for Kelly, it proposed
   `name: Kelly` — it had never asked for a name and used the one in front of it. Fixed in
   the prompt *and* guarded in the loop, because this is precisely the kind of thing that
   comes back. The guard routes through the repair path, so the player never sees it.
3. **Backstory facts were never recorded.** The player said why she left the temple — the
   best hook in the conversation — and no `[[FACT:]]` was written, because the prompt put
   backstory work *after* the sheet and the sheet arrived in the same reply. Facts are now
   recorded from the first exchange. In the re-run both details landed in the ledger.

Also two display bugs, both player-facing and both invisible to mocks: the GM wraps the
proposal in a code fence, so stripping the tag left an empty ``` ``` on screen; and the
whitespace around a suppressed tag stayed behind, leaving a hole mid-reply. Both fixed and
pinned.

**Running tally: four tasks in a row where the mocks passed and only the live call found
the problem.** P1.1 `fallbacks`, P1.2 the canon leak, P1.3 display + continuity, P1.4
these five. This is now a reliable enough pattern that a task without a live run should be
treated as unfinished.

### Deviations

1. **Allocation by ranking rather than by proposed scores** — beyond the letter of D-005,
   which says the GM handles allocation mechanics. Flagged as **OD-13** below.
2. **The creation transcript accumulates**, unlike play's rebuilt-every-turn prompt.
   Flagged as **OD-14** below.
3. **`_NarrationStream` now filters on `[[` rather than on `[[CHECK`.** P1.4 added two
   more tags, and a filter that must be updated per tag is one that eventually misses one
   in front of a player.
4. **Creation events reuse `gm_narration` with `scene: "character creation"`** rather than
   a new event type. D-008 says extend the vocabulary in the doc first, and that needs a
   ruling; an existing optional field carried the distinction without one.

### Known issues / notes

- **D-006 scaffolding does not reach creation.** Co-creation is always fully guided
  (D-005), and the scaffolding templates are written in terms of in-play action options,
  so reusing them read badly. An experienced player's third character may want less
  hand-holding.
- **Background grants no skills.** SRD 5.1 backgrounds are not in the ingested dataset, so
  `background` is narrative text and skills come from the class list only. Real 5e gives
  two more. Worth a data task before it distorts a playtest.
- **Starting equipment is not SRD data.** `starting_equipment` came through empty from
  ingest, so gear is free text with no weight unless it is armour or a shield. Encumbrance
  is therefore wrong-ish, which nothing reads yet.
- One character per run; two players means two runs. Fine for a table of two.
- `CanonWrite.scope`'s doc comment lists `pc_fact`, but `CanonScope` says `character`, and
  I emit the enum value so the event and the ledger agree. The comment is stale — worth a
  one-line fix whenever D-008 is next opened.

### Recommended next task

**P1.5 — first playtest (Kelly + Sam).** Everything it needs now exists: a campaign, real
co-created characters, the turn loop, canon, and cost telemetry. This is the one task I
cannot do — it wants the two of you at the keyboard. Suggested shape: `dndc new-campaign`,
one `create-character` run each, then a session of maybe an hour, with findings written to
`docs/playtests/` and design questions tagged `FOR DESIGN:`.

Phase 2 (canon ledger + memory) is the next thing I can pick up, and it will be better
informed after a playtest — the extraction pass has real transcripts to be right about.

**FOR DESIGN:** two rulings wanted, neither blocking.

**OD-13 — allocation by ranking.** D-005 says the GM "handles allocation mechanics
(standard array/point-buy...) *for* the player". I read that through OD-12 and had it
propose an ordinal priority instead of scores, with the engine assigning the array. It is
stronger than the text requires and it makes illegal spreads unrepresentable rather than
caught — but it does constrain the GM: it cannot, for instance, deliberately build an
unusual spread that fits a concept ("she's strong *and* clever, and frail in every other
way" is expressible; "two 14s and nothing else remarkable" under standard array is not,
since the array's shape is fixed). My read is that this is the right trade at level 1 for
a household table, and that if a concept genuinely needs a different shape the answer is
another named point-buy shape rather than free-form numbers — the same "richer engineered
signal, never restore the integers" remedy OD-12 prescribes. Confirm, or tell me to let
the GM propose scores and have the allocators reject illegal ones.

**OD-14 — the creation transcript accumulates.** D-002 says the prompt is rebuilt every
turn from ledger + chronicle + recent window, never a growing transcript, and that is
about campaign-scale cost. A creation interview is a dozen exchanges, is bounded by its
own completion, genuinely needs its history (backstory built on turn nine refers to turn
two), and is then thrown away — so I let it accumulate and noted the exception in the
module docstring. Measured cost of a full character is ~$0.05. I believe this is inside
the spirit of D-002 rather than an exception to it, but it is the first place the codebase
keeps a conversation, so it should be said out loud rather than assumed.

---

## 2026-08-05 — P1.3 turn loop + OD-11 (Claude Code, kelly-pc)

**Completed: P1.3**, and **OD-11 implemented** as ruled. 411 tests passing (44 new), suite
still offline. Verified live end to end: a full turn with a check costs ~$0.012 on Sonnet.

### OD-11 — implemented structurally, not by instruction

The ruling bans engine-resolved numbers from the GM's prose and puts **severity fidelity**
in their place. Both halves are in:

- `rules/severity.py` turns an outcome into a band — `succeeded decisively`, `failed, but
  only just`, `gravely wounded and barely standing`. Damage severity is relative to the
  character's maximum, because 6 damage is a scratch to one PC and near-lethal to another,
  and the players' felt sense should track the second reading.
- **The GM is never handed a number at all.** `describe_check` produces "Brannoc's
  athletics check failed, but only just." — the roll, the DC, and the modifier never enter
  the prompt. A model cannot restate a value it was never given, so the ban holds by
  construction rather than by the GM remembering an instruction on turn 90. A test asserts
  no engine value appears anywhere in the second call's prompt.
- The prompt carries the rule anyway (belt and braces), including Fable's narrative-quantity
  carve-out — three goblins and fifty gold are still the GM's to narrate.
- The CLI renders the numbers from state, in ASCII, under the narration.

Observed working live: a check missed DC 15 by one, the engine said "failed, but only
just", and the GM wrote *"for a heartbeat you feel the bar shift — just a whisper of
movement — then your grip slips."* Severity and prose tracked without a number crossing
the boundary.

### The loop

`game/turn.py`. A turn is at most two GM calls: the first considers the action and either
narrates or asks for a resolution; the engine resolves; the second narrates the outcome.
TASKS.md's "intent pre-check" is the GM's own judgment expressed as `[[CHECK: ...]]` —
which is exactly D-001's boundary rule, with the DC logged as a `gm_adjudication` so Phase
7 can audit whether the rulings were fair.

`gm/checkrequest.py` parses the tag. Forgiving about surface form (dash style, `DC15`,
casing, bare skill vs `Dexterity (Stealth)`) because the producer is a language model and
losing a turn to an en dash is a bad trade — but **strict about meaning**: a missing DC
raises rather than inventing the difficulty the GM was supposed to set. Where the GM pairs
a skill with the wrong ability, the SRD mapping wins; that is rules data, not a judgment
call.

`dndc play` is the hot-seat loop (OD-4): active player in the prompt, `/switch`, `/who`,
`/scene`, `/recap`, `/quit`.

### Three findings from running it

1. **The `[[CHECK: ...]]` tag was streaming to the players.** It is machine instruction,
   and it appeared mid-scene in front of the table. There is now a streaming filter that
   holds text from the first `[` and releases it as soon as it cannot be a tag, so ordinary
   bracketed prose still passes. Tested against tags split across chunk boundaries, which
   is how real streaming actually arrives.
2. **The second call restaged the first.** The player read the same moment twice — "you
   hook your fingers under the bar" then "you jam your fingers into the gap". Fixed by
   feeding the GM its own lead-up back as an assistant message plus a follow-up
   instruction to continue rather than restate (`prompts/resolution.md`). The scene now
   reads as one continuous paragraph across the two calls.
3. **OD-9's pairing could not actually work as built.** P1.1 minted `call_id` *inside* the
   backend, so the `pending` row — written before the call — could never carry it. The id
   is now minted by the caller and echoed by every adapter (`GMRequest.call_id`), which is
   what OD-9 asked for. A crashed call also now writes a `failed` terminal row; without it
   a crash is indistinguishable from a call still in flight.

### Deviations

1. **`GMRequest.call_id` added** — a P1.1 API change, made because OD-9's requirement was
   otherwise unimplementable (see finding 3). Backends mint one when the caller does not,
   so nothing else changed.
2. **`rules/severity.py` is new and not in the task text.** OD-11's severity-fidelity
   clause needs a signal to track, and computing it deterministically is what lets the GM
   be told "how bad" without being told "how much".
3. **The GM receives severity instead of raw results.** The ruling bans restating numbers;
   withholding them is a stronger reading than the letter requires. Flagged for Fable
   below — it is the one place I went past the text of the ruling rather than up to it.
4. **`gm_adjudication` is written after its `rules_resolution`.** The ruling logically
   comes first, but D-008 wants `resolution_seq` on the adjudication and the log is
   append-only — writing it after is what makes that link exact instead of a second
   patch-up row. Nothing external happens between them, so there is no crash window.

### Known issues / notes

- `MAX_GM_CALLS = 2`. A GM that keeps asking for rolls is a prompt bug, and an unbounded
  loop would spend real money discovering it. A second request in one turn is ignored.
- Only ability checks and saves route to the engine. Attacks and damage exist in
  `rules/checks.py` but nothing requests them until Phase 3.
- `MechanicalResult.render()` is deliberately ASCII: rich's legacy Windows console path
  raised `UnicodeEncodeError` on `→` and took the whole line down. The numbers are the one
  thing that must survive a bad console.
- Campaign state still comes from CLI flags rather than `campaigns/<slug>/`. Wiring that up
  belongs with Phase 2's persistence.
- The hot-seat active player is sticky, not rotating — `/switch` hands over explicitly.
  Rotation would be wrong during exploration, where one player often acts several times.

### Recommended next task

**P1.4 — guided character co-creation (D-005)**: interview flow → concept → GM proposes an
allocation via the P0.4 allocators → backstory collaboration → validated sheet → backstory
facts written as canon entries. The pieces are all present now: `assign_standard_array` /
`assign_point_buy` from P0.4, the `CanonEntry` type with a `character` scope already
defined for exactly this, and a turn loop to run the interview in. It is also what removes
`--character` as a prerequisite for `dndc play`.

**FOR DESIGN:** deviation 3 above wants a sanity check. OD-11 says the GM must not restate
engine values; I implemented it by not giving the GM the values at all, substituting a
severity band. That is strictly stronger, and it makes the ban structural — but it does
remove information the GM might legitimately use, and Phase 3 is where that could bite: a
GM narrating combat cannot say "you are one hit from going down" if it only knows
"seriously wounded". My read is that the severity vocabulary should simply grow richer for
combat (it already distinguishes "gravely wounded and barely standing") rather than the
numbers coming back. Confirm, or tell me to hand over the raw results and rely on the
prompt rule.

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
