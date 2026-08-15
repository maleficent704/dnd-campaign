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

**Amended 2026-08-05 (per OD-11).** The GM narrates engine outcomes **qualitatively
only**: it never restates engine-resolved mechanical values (damage numbers, HP,
roll totals, DCs, modifiers) in prose — the CLI renders those authoritatively from
state beside the narration, so there is exactly one numeric source of truth on
screen and no transcription-desync side door. Scope: the ban covers engine state,
not narrative-world quantities ("three goblins", "fifty gold" remain legal story
facts). Corollary obligation: **severity fidelity** — with numbers removed, prose
is the players' felt sense of magnitude, so description must track it (a
2-damage scratch reads as a scratch; a near-drop reads as dire).

**Amended 2026-08-05 (per OD-12).** The number ban is **structural**: the GM is never
handed engine-resolved values at all — it receives deterministic categorical/ordinal
signals (severity bands, computed relative to the right baseline, e.g. damage vs. the
character's max HP) and cannot restate what it was never given. Protection by
construction over protection by instruction, same as the mystery's
cover-substitution lesson. Governing principle for Phase 3+: **if the GM appears to
need raw numbers, the boundary is misdrawn** — exact integers are only needed for
arithmetic, and arithmetic is the engine's job; every legitimate GM judgment is
ordinal/categorical, so the remedy is a richer engineered signal (or moving the
decision into the engine), never restoring the integers.

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

**Amended 2026-08-04 (per OD-10 + P1.1 measurement).** (1) **Credential isolation is a
ratified requirement:** the `subscription` adapter must strip `ANTHROPIC_API_KEY` and
`ANTHROPIC_AUTH_TOKEN` from the child environment so headless CC cannot silently
resolve to the metered key (credential precedence otherwise inverts the toggle);
never read or copy the stored OAuth refresh token. Pinned by test. (2) **Measured
reality replaces the light-week rationale:** headless CC carries ~33–40k tokens of
scaffolding per invocation (~30× overhead; ~4M pool tokens per 3-hour session), while
a metered session measures ~$0.50–2. Subscription mode is therefore the
"pool-is-genuinely-idle / free experimentation" path, not the bargain path; **sticky
default is `api`** for play sessions. Toggle retained — it is measured, tested, and
re-evaluable from telemetry.

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

**Amended 2026-08-05 (per OD-13 + OD-14).** (1) **Allocation is by ranking:** the GM
proposes an ordinal priority over the six abilities (or a named point-buy shape); the
engine assigns actual scores. Illegal spreads are unrepresentable, the GM never sees
or states a number (consistent with D-001/OD-12), and a concept needing an unusual
spread gets a new named shape — never free-form numbers. (2) **The creation interview
is a scoped exception to D-002's no-transcript rule:** it keeps its own full history
because it is bounded by its own completion, needs its history (late backstory refers
to early answers), and is discarded afterward (~$0.05/character measured). This
exception covers character creation only and is not precedent for play prompts.

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

**Amended 2026-08-05 (per OD-15, from the first play session).** (1) Fading is
**player-initiated**: a `/scaffolding high|low|off` command changes the level
mid-session; no automatic fading — detecting "the player ignored the options" is a
fuzzy lexical judgment of the kind npc-village showed to be unreliable, and the
ignore-rate is in the logs for Phase 7 to revisit with data. (2) **Meta lives in the
chrome:** the CLI, not the GM's prose, occasionally hints that the command exists —
extending OD-11's split (fiction in prose, interface in chrome). (3) At every level
the template owes **phrasing variety**: the option menu may be a fixture, its closing
sentence may not (first session: 23/32 replies ended with the identical sentence).

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
*(Amended 2026-08-09 by CC, ratified 2026-08-10: `canon_write.scope` = the `CanonScope`
enum; `canon_write.operation` gains `conflict` — narration contradicted an entry and
the entry was kept; `inventory_change`; `chronicle_write` as a separate family so a
lossy summary cannot enter the ledger as fact.)*
*(Amended 2026-08-10 per OD-16: subscription-mode `cost` / `would_have_cost` values
are recorded raw as provider-reported but measure the headless-CC harness, not the
campaign — they are excluded from campaign cost analysis; all campaign cost claims
come from `api` runs only.)*
*(Amended 2026-08-12 by CC for P2.3: `canon_write` gains `source` and `confirmed` —
the end-of-session sweep is a second ledger writer on a cheaper tier, and a row that
cannot say who wrote it cannot be weighed.)*
*(Amended 2026-08-13 by CC for P2.4: the `[[GAIN:]]` / `[[LOSE:]]` wire format is
specified here, and `inventory_change` gains `applied` — "the table said yes" and "the
sheet changed" are different facts, and the gap between them is the desync Finding 5
was about.)*
*(Amended 2026-08-15 by CC for P3.3: combat. `combat_start`, `combat_turn`,
`hit_point_change` and `combat_end`; attacks, damage rolls, death saves and initiative
stay `rules_resolution`, whose `kind` field named them in the original ruling.)*
*(Amended 2026-08-15 by CC for P3.7: the `[[TARGET:]]` tag, and `combat_turn` gains
`target` / `target_source` so a logged fight says whether the GM chose, defaulted, or had
its choice overtaken by events.)*

**Amended 2026-08-09 (Phase 2, doc-first per this decision's own rule).**

1. **`canon_write.scope` values are the `CanonScope` enum**, not the free-text list the
   schema comment carried: `world` · `player_known` · `gm_only` · `npc_belief` ·
   `character`. The old comment named `world_truth`, `quest_state` and `pc_fact`, none of
   which were ever written by code. (Fable queued this correction at the P1.4 handoff for
   the next D-008 touch; this is it.)
2. **`canon_write.operation`** takes `create` · `supersede` · `conflict`. `supersede`
   pairs with the existing `supersedes` field. **`conflict` records that new narration
   contradicted an existing entry and the entry was kept** — the ledger never silently
   updates itself to match drift, because measuring drift is the point (see the Phase 2
   contradiction rule, ratified 2026-08-10).
3. **New event family `inventory_change`** — item acquisition and loss, per the
   2026-08-05 ruling that items are state and acquisition joins canon extraction. Fields:
   `character`, `item`, `quantity` (default 1), `direction` (`gain` | `lose`),
   `established_by` (the GM tag that proposed it), `confirmed` (bool — the player or CLI
   agreed), `turn_seq`. A *rejected* proposal is still logged, with `confirmed: false`;
   what the GM proposed and the table declined is exactly the kind of thing Phase 7 wants.
4. **New event family `chronicle_write`** — one entry per compression pass (D-002's third
   layer). Fields: `covers_sessions` (list), `summary`, `model`, `token_estimate`.
   Separate from `canon_write` because a chronicle entry is lossy prose about many turns,
   where a canon entry is a discrete fact with provenance; conflating them would let a
   compression artifact enter the ledger as an established fact.

**Amended 2026-08-12 (P2.3, doc-first per this decision's own rule).** The end-of-session
sweep gives the ledger a *second* writer, on a different model tier and at a different
level of trust, so `canon_write` has to say which one wrote a row.

5. **`canon_write.source`** — the mechanism that established the fact: `gm_tag` (the GM's
   inline `[[CANON: ...]]`), `sweep` (the end-of-session utility-tier backstop),
   `co_creation` (D-005 backstory facts), `authored` (hand-written into `canon.yaml`).
   Without it, "how much of this ledger was written by a local 8B?" is a string match on
   `established_by` — and that question is the whole reason the sweep needs measuring.
6. **`canon_write.confirmed`** — as `inventory_change.confirmed`, for the same reason and
   with the same semantics. A sweep proposal the table declined is logged with
   `confirmed: false` and **never enters the ledger**; the GM's own tags and co-creation
   facts are `true`. What a model proposed and the humans rejected is a measurement of
   the proposer, and it is only available if the rejection is written down.

**Amended 2026-08-13 (P2.4, doc-first per this decision's own rule).** The 2026-08-05
ruling left the wire format to CC and required it be written down before it is built.

7. **The tag the GM writes** is, on its own line:

   ```
   [[GAIN: <character> — <item> ×<quantity>]]
   [[LOSE: <character> — <item> ×<quantity>]]
   ```

   Character and quantity are both optional — `[[GAIN: a tallow candle]]` is well-formed
   and means one, for whoever is acting. Two verbs rather than one tag with a direction
   field, because `[[INVENTORY: gain ...]]` is a form the GM can get subtly wrong (a
   missing or misspelled direction would have to be guessed, and guessing which way an
   item moved is worse than any parse failure). It is the fifth use of the `[[TAG:]]`
   convention `[[CHECK]]` established, and the `[[`-suppressing stream filter already
   keeps it off the players' screens.

   The parser is forgiving about surface form and **strict about direction and item** —
   a tag naming no item is dropped rather than guessed at, the `[[CHECK]]` posture rather
   than the `[[CANON]]` one. A dropped canon fact costs the ledger a line; a guessed item
   change writes fiction into the sheet, which is the failure this task exists to fix.

8. **`inventory_change.applied`** — whether the sheet actually changed as proposed.
   `confirmed` says the humans agreed; `applied` says the engine could do it. They come
   apart when the GM narrates losing something the sheet never had, or more of it than
   the sheet holds — which is precisely the fiction/state divergence Finding 5 recorded,
   so it needs to be visible as a field and not inferred from a join nobody will write.
   The change still happens as far as the sheet can honour it (phantom items left behind
   because the narration was ahead of the sheet is the worse failure); `applied: false`
   is the flag that says the two did not match.

**Amended 2026-08-15 (P3.3, doc-first per this decision's own rule).** Combat. Written
*after* P3.1 and P3.2 rather than alongside them, deliberately: a vocabulary invented
before a fight has ever run describes the code instead of the game.

**First, what needs nothing.** `rules_resolution.kind` was specified in 2026-07-27 as
`check | save | attack | damage | initiative | roll`, which already covers every die a
fight rolls. Attack rolls, damage rolls, death saves and initiative rolls are
`rules_resolution` rows and no new family is added for them — the field has `actor`,
`target`, `dc` (a target's AC is a DC), `critical` and `seed`, which is the whole of what
an attack needs. A death save is `kind: "save"` against DC 10 with no ability, which is
exactly what a death save is in the rules.

Four families are genuinely new, and they are separate types rather than one `combat`
family with a `phase` field so that a wrong-shaped row is unrepresentable rather than
merely discouraged — the same construction-over-instruction stance as OD-11 and OD-12.

9. **`combat_start`** — the roster *as instantiated*, the initiative order, and the seed.
   Load-bearing for replay: monster hit points may be rolled (P3.2), so without this row
   the combatants cannot be reconstructed and every later row in the fight refers to
   creatures of unknown durability. Fields: `encounter_id`, `combatants` (id, name, side,
   max/current HP, AC, whether a player), `order` (combatant ids, first to last),
   `seed`, `round` (always 1).

10. **`combat_turn`** — `encounter_id`, `round`, `combatant`. Derivable in principle from
    the initiative order and the rows between; derivable-in-principle is where analysis
    goes wrong, and one cheap row per turn makes "which round was this narration in" a
    lookup rather than a simulation. Phase 7 will ask how long fights run and whether
    narration degrades by round.

11. **`hit_point_change`** — the state change, as distinct from the roll that caused it.
    The `inventory_change` argument exactly: the engine performs a change to a sheet the
    GM must never invent, and it has to be visible as its own row. Fields: `combatant`,
    `before`, `after`, `amount` (positive for damage, negative for healing), `damage_type`,
    `effect` (`normal | resistant | vulnerable | immune`), `temporary_absorbed`,
    `dropped`, `killed`, `resolution_seq` pointing at the `rules_resolution` that rolled
    it — the same link `gm_adjudication` already uses. Separate from the roll because the
    two genuinely come apart: a fall damages with no attack roll, and resistance changes
    what a roll means without changing the roll.

12. **`combat_end`** — `encounter_id`, `outcome` (`party | foes | draw`), `rounds`,
    `survivors`. A fight's length and lethality are the numbers Phase 3 exists to make
    measurable.

**Which fight a roll belongs to** goes in `rules_resolution.detail["encounter"]`, not in
a new field. `detail` is already the per-kind extras bag, three of the six `kind` values
never occur in combat at all, and widening a family shared with every check in the game
for something only combat needs is the wrong trade. Death saves also carry their running
tally there (`successes`, `failures`, `revived`, `stabilised`, `died`) — the roll is one
fact and how close to dead it left someone is another, and a reader should not have to
count backwards through the log for it.

**Amended 2026-08-15 (P3.7, doc-first).** Monster tactics become the GM's, per the
2026-08-15 (c) ruling: target selection is categorical judgment, and replay is preserved
the way DCs already are — by logging the judgment and reading it back rather than
re-asking.

13. **The tag the GM writes**, on its own line, in any narration during a fight:

    ```
    [[TARGET: <monster> -> <target>]]
    ```

    A *declaration of intent for a turn that has not happened yet*, which is what makes it
    cost nothing: the GM already gets one call per turn to narrate, and it has just been
    shown the state, so it is better placed to say who the wolf goes for next than it
    would be in a call of its own. Names are matched with the same tiered matcher
    `/switch` uses; an unmatched name is not a guess.

14. **`combat_turn` gains `target` and `target_source`** (`declared` | `policy` |
    `stale`). `declared` is the GM's choice honoured; `policy` is the deterministic
    fallback because nothing was declared; `stale` is a declaration that named someone
    already down or absent, so the fallback ran instead. **The fallback is always logged
    as a fallback** — a fight must never stall on a missing tag, and Phase 7 must never
    have to guess whether a choice was made or defaulted.

    That third value is the one worth having. A declaration written a turn ahead can be
    overtaken by events, and "the GM chose badly" and "the GM's choice expired" are
    different findings.

**Deliberately not added: `condition_change`.** Conditions exist in the combat core and
almost nothing consults them yet (P3.4 owns that). A family nothing emits is vocabulary
ahead of code, which is the failure this amendment's own timing was chosen to avoid.

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
