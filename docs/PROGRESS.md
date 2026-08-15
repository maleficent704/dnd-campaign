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

**None.** (The 2026-08-14 block below is ruled; both CC-owned items — the utility seat
split and the sweep's display grouping — were implemented 2026-08-15.)

*(OD-15 was ruled 2026-08-05 and implemented 2026-08-09 — see below.)*

### Protocol in effect (Fable, 2026-07-27)

- **The docs are the channel.** No copy-paste through Kelly. Session start: read this
  file from the top, apply new rulings before code. Session end: dated handoff entry,
  `FOR DESIGN:` tags for anything needing a ruling. Work isn't done until the entry
  exists.
- **A Fable ruling takes effect only once recorded in the repo.**
- **One session, one commit. No code edits under a live play session.**

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

## 2026-08-15 — Fable's 08-14 rulings applied: the seat split and proposal grouping (Claude Code, kelly-pc)

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
