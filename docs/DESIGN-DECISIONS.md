# DESIGN-DECISIONS.md — D&D Campaign Companion

Ratified decisions with rationale. Do not contradict without flagging. Companion to the
phase plan in `race-control/docs/planning/active/2026-07-27-dnd-campaign-companion.md`
(OD-1…OD-6 register lives there; decisions below carry the same rulings in build-ready
form). Origin: FE-03 in `llm-murder-mystery/docs/DESIGN-DECISIONS.md`.

---

## D-001 — Four-tier orchestra; mechanics never touch a model

**Ruling.** All game mechanics — dice, checks, combat resolution, initiative, HP,
slots, inventory, encounter math — are deterministic Python over structured SRD data.
LLMs receive mechanical *outcomes* to narrate; they never produce or adjudicate
numbers. Tiers: (1) deterministic core, (2) GM brain (Claude), (3) NPC voices (local
70B), (4) utility (local 8–12B).

**Rationale.** The mystery proved LLMs are strong at voice, weak at bookkeeping
(alibi mutation without the claims ledger; confabulation cascades). 5e mechanics are
fully specifiable, so the cheapest and most consistent component is also the correct
one. This is the primary cost lever: the expensive model runs only where judgment and
prose are genuinely needed.

**Rejected.** LLM-adjudicated combat ("GM rolls in its head") — non-reproducible,
drift-prone, expensive, and destroys the research value of the logs.

**Boundary rule.** The GM may *request* a mechanical resolution (e.g., "this stunt is
a DC 15 Acrobatics check") but the engine computes it. GM-set DCs are logged as
adjudication events so ruling fairness is analyzable (D-008).

---

## D-002 — Canon ledger + three-layer memory (ported)

**Ruling.** Campaign continuity uses three layers, ported from npc-village's memory
model: (1) **session log** — raw JSONL event stream; (2) **canon ledger** — typed,
structured facts: world truths, NPC knowledge scopes, quest state, established lore,
player-character facts; (3) **campaign chronicle** — compressed narrative summaries
(utility tier writes these between sessions). The canon ledger generalizes the
mystery's claims ledger: entries carry provenance (which session/turn established
them) and scope (world-truth vs NPC-belief vs player-known).

**Rationale.** The claims ledger is the single most load-bearing finding from the
mystery — without it, established facts mutate within one session. A campaign is
dozens of sessions; the ledger is what makes "campaign" possible at all. Provenance
enables the Phase 7 canon-drift instrumentation.

**Prompt rule.** The GM prompt is rebuilt every turn from ledger + chronicle +
recent-window, never from a growing transcript. This bounds cost and is the same
protection-by-construction stance the mystery director takes.

---

## D-003 — GM is director + gatekeeper; NPCs are gated agents

**Ruling.** The GM component owns ground truth and rebuilds every NPC prompt per turn
containing only what that NPC's knowledge scope permits (cover-substitution, not
"don't mention X" prohibitions). NPC drafts pass a gatekeeper check before display.
Stance-scoped supersession (mystery OD-13 machinery) applies when the GM changes what
an NPC knows or believes.

**Rationale.** Direct reuse of proven mystery machinery — the defense against
confabulation cascades and knowledge leaks. Secrets in a campaign (the villain's
identity, the twist) are structurally identical to suspect secrets.

**Reuse mapping (from FE-03):** director → GM brain · gatekeeper → NPC output gate ·
claims ledger → canon ledger · revelation tiers → plot-secret unlock conditions ·
threshold-moment cues → threshold-moment escalation (D-004) · JSONL event stream +
session_meta → same, extended (D-008).

---

## D-004 — GMBackend dual adapter with session-start billing toggle

**Ruling.** One `GMBackend` interface, two adapters: **`api`** (Anthropic Python SDK,
key from `.env`, metered, console spend cap ~$20–25/mo) and **`subscription`** (Agent
SDK / headless CC under the household Max login). The CLI asks at session launch —
or takes `--billing api|sub` — with a sticky default. Subscription mode prints a
throttling heads-up (weekly pool may run dry mid-session). Model tiering: Sonnet-class
default; escalation to Opus at authored threshold moments only. Both adapters report
token usage into the event stream; subscription sessions log *would-have-cost* at API
rates so the toggle's value is measurable.

**Rationale.** The separate Agent SDK credit is not active on Kelly's account
(verified 2026-07-27) — SDK usage bills to subscription limits. Household usage varies
weekly (heavy build weeks vs light ones), so the billing choice belongs at session
granularity, not architecture time. The interface keeps the engine ignorant of the
difference and robust to Anthropic billing changes (two changes in 2026 already).

**Rejected.** Single-path API-only (wastes paid-for subscription capacity on light
weeks); single-path subscription-only (couples play sessions to build-week limits;
mid-boss throttling risk).

---

## D-005 — Character creation is guided co-creation

**Ruling.** Character creation is a conversational GM-led interview per player. The GM
handles allocation mechanics (standard array/point-buy, proficiencies, equipment)
*for* the player based on their expressed concept, proposes and collaboratively
develops backstory, and the deterministic engine validates + emits the final sheet.
The conversation is the UX; the sheet is the output. Sheets are re-editable data
(`campaigns/<name>/characters/*.yaml`).

**Rationale.** Both players asked for exactly this: help with point allocation and
Claude's storytelling strength on backstory. Backstory elements feed the canon ledger
at campaign start (typed as player-character facts), which gives the GM hooks to pay
off later — the thing human GMs do that makes campaigns feel authored.

---

## D-006 — New-player scaffolding, BG3-style, fading

**Ruling.** Early sessions, the GM proactively surfaces concrete options ("you could
sneak past, talk your way in, or look for another entrance — or anything else you can
think of") the way a video game UI does, and *always* signals that the menu is not
exhaustive. Scaffolding level is a campaign setting (`scaffolding: high|low|off`) the
GM can lower over time or on request.

**Rationale.** Both players are BG3-fluent but new to open-ended tabletop play; "what
can I do?" is the expected early friction. A good human GM does this instinctively for
new players. Making it an explicit, tunable behavior costs one prompt-template
parameter and prevents the most likely early-session stall.

---

## D-007 — SRD 5e (CC-BY-4.0); original campaign content only

**Ruling.** Rules content comes exclusively from the D&D 5e SRD, used under its
Creative Commons Attribution 4.0 license; the attribution notice ships with the data
in `data/srd/`. Record the exact source + version of whatever SRD dataset is ingested.
All campaign/story content is original, generated for this table. Never ingest or
reproduce published adventure modules, non-SRD monsters/subclasses, or other
copyrighted game text.

**Rationale.** Legal cleanliness with zero gameplay cost — the SRD covers the full
core loop — and original campaigns are the point of having a generative GM anyway.

---

## D-008 — Event vocabulary + cost telemetry

**Ruling.** Append-only JSONL per session. Event families: `session_meta` (includes
commit SHA, `dirty_worktree` flag, backend choice, models per seat), `player_input`,
`rules_resolution` (rolls, DCs, outcomes — fully reproducible), `gm_adjudication`
(DC-setting, creative rulings), `gm_narration`, `npc_turn` (with gatekeeper verdict),
`canon_write` (ledger mutations with provenance), `escalation` (threshold-moment Opus
calls + trigger), `cost` (per-call tokens + dollars; would-have-cost in subscription
mode). Model-call events (`gm_narration`, `npc_turn`) carry `CallStatus`
(`pending`/`complete`/`failed`) — intent is logged before the external call — and a
`call_id` (uuid) shared by the pending and terminal writes so pairing is exact even
under interleaved calls (Phase 4 runs two Ollama endpoints); `cost` events carry the
same `call_id`. Extend the vocabulary here first, then in code.
*(Amended 2026-08-04 per OD-9: CallStatus, call_id, dirty_worktree ratified.)*

**Rationale.** Same discipline as the mystery; the additions (canon_write provenance,
cost, escalation) are what Phase 7's instruments — canon-drift measurement, ruling
logs, cost-per-session — consume. Pending-state logging lesson from the mystery
applies: log intent before external calls so crashes are reconstructable.

---

## OD register (mirror)

OD-1 ruleset=SRD 5e · OD-2 dual-backend toggle (→D-004) · OD-3 Sonnet default/Opus
threshold (→D-004) · OD-4 hot-seat until Phase 6 · OD-5 runtime on kelly-pc,
Ollama endpoints toto-llm + sam-pc in config · OD-6 guided co-creation (→D-005).
All ratified 2026-07-27. Canonical text: the race-control planning doc.
