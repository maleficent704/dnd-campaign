# TASKS.md — phased build plan

Work in order unless PROGRESS.md's latest handoff says otherwise. Each phase is
independently executable cold from the scaffold docs. Definition of done for any task:
code + tests + a PROGRESS.md handoff entry.

## Phase 0 — Scaffold, SRD, dice, sheets (no LLM) — **COMPLETE 2026-08-04**

- **P0.1** Repo init: `pyproject.toml` (py3.11+, pydantic, pyyaml, rich, pytest),
  `.gitignore` (logs/, .env, __pycache__, campaigns/*/saves if large), package
  skeleton per CLAUDE.md layout. Run `scripts/install-hooks.sh`. First commit.
- **P0.2** SRD ingestion: fetch a CC-BY 5e SRD structured dataset (record exact
  source, version, license text in `data/srd/ATTRIBUTION.md`), normalize into typed
  pydantic models (races/species, classes L1–5 minimum, spells, monsters CR 0–5,
  equipment, conditions). Validator + `dndc srd stats` sanity command.
  *(Scope note: L1–5 / CR 0–5 covers a starting campaign; widen later as data tasks.)*
- **P0.3** Dice + rules primitives: dice expression parser (`2d6+3`,
  advantage/disadvantage), ability checks, saves, attack resolution, seeded RNG for
  reproducible tests. Pure functions; property tests.
- **P0.4** Character sheet schema + validator: full L1 sheet (abilities, skills,
  proficiencies, HP, AC, inventory, spell slots), standard array + point-buy
  allocators as pure functions (the co-creation flow calls these in Phase 1).
  Round-trip YAML.
- **P0.5** CLI skeleton (`dndc` entry point, rich): `new-campaign`, `roll`,
  `sheet show/validate`. JSONL logger with `session_meta` (commit SHA, config).

## Phase 1 — Core play loop + co-creation (first playable)

- **P1.1** Model adapters: `GMBackend` interface; `api` adapter (Anthropic SDK,
  streaming, prompt caching, usage capture); `subscription` adapter (Agent SDK /
  `claude -p`, usage capture, would-have-cost calc); Ollama adapter (OpenAI-compat)
  for later tiers. Mock backend for tests. Session-start billing prompt + `--billing`
  flag + sticky default in config (D-004). Subscription-mode throttle warning.
- **P1.2** GM prompt assembly v1: system template (tone, D-006 scaffolding parameter,
  never-invent-mechanics rule), context builder (canon ledger stub + recent window),
  templates in `src/dndc/gm/prompts/`.
- **P1.3** Turn loop: player input → intent pre-check (does this need a rules
  resolution? engine resolves → hand outcome to GM) → GM narration → log events.
  Hot-seat prompt indicates active player. *(Done 2026-08-05 — `dndc play`; the
  pre-check is the GM's own `[[CHECK: ...]]` request, parsed and routed to the engine.
  OD-11 implemented here too: severity bands to the GM, numbers to the interface.)*
- **P1.4** Guided character co-creation (D-005): interview flow → concept → GM
  proposes allocation via P0.4 allocators → backstory collaboration → validated sheet
  → backstory facts written as canon entries (typed player-character facts).
  *(Done 2026-08-05 — `dndc create-character`; the GM proposes an ability **ranking**
  and the engine assigns the array, per OD-12. `dndc play --campaign SLUG` now loads
  the party and canon from disk, so `--character` is optional.)*
- **P1.5** First playtest session (Kelly + Sam): a short original scenario authored by
  the GM at runtime. Findings to `docs/playtests/`; tag design questions `FOR DESIGN:`.
  *(Done. Solo 2026-08-05 — Kelly + Corin Vale, 29 turns, $0.50;
  `docs/playtests/2026-08-05-first-play-session.md`. Two-player 2026-08-07 — Kelly +
  Sam in *The Salt Road*, 8 turns, 70 min;
  `docs/playtests/2026-08-07-two-player-session.md`. Hot-seat rotation works;
  `/switch` name matching fixed 2026-08-09.)*

**Phase 1 complete 2026-08-09.** Also landed here: OD-15's `/scaffolding high|low|off`
command, CLI hint, and template phrasing variety (D-006 as amended).

## Phase 2 — Canon ledger + memory (D-002)

Typed canon ledger with provenance + scopes; GM extraction pass writing `canon_write`
events; chronicle compression job on utility tier; prompt builder consumes
ledger+chronicle+window (never full transcript). Drift test: replay a logged session,
assert ledger stability. **Added per OD-15-session rulings (2026-08-05): item
acquisition/loss — GM proposes via a `[[GAIN/LOSE]]`-style tag (the `[[CHECK]]`
precedent), player/CLI confirms, engine mutates the sheet, event logged (doc-first
per D-008); plus the `/scaffolding` command + CLI hint + phrasing variety per
amended D-006 — `/scaffolding` shipped 2026-08-09 with Phase 1. The archived Ashmill
log (TrueNAS) is the before-picture fixture for the drift test.**

Task breakdown (D-008 amended 2026-08-09 for all four vocabulary changes below):

- **P2.1** Ledger machinery: supersession (`supersede`), the contradiction rule
  (`conflict` — canon wins, entry kept, conflict logged, **never a silent overwrite**),
  stable id minting, and ledger persistence into the campaign directory so what play
  establishes survives the process. *Scoping note: this makes the **world** survive, not
  the transcript — resuming a session mid-scene is Phase 5.*
  *(Done 2026-08-10. `CanonStore` in `src/dndc/memory/canon_store.py` owns the ledger,
  the file, and the log; saved atomically on every write, not at session end.)*
- **P2.2** Inline extraction: the GM emits `[[CANON: ...]]` as it narrates and the engine
  writes the entries. Chosen over a per-turn extraction call (~2× cost) and over
  end-of-session-only (canon absent during the session that established it); it is the
  fourth use of the tag convention `[[CHECK]]` established, and the `[[`-suppressing
  stream filter already hides it from players.
  *(Done 2026-08-10 — `src/dndc/gm/canontag.py`, extraction at the single choke point in
  `turn.py::_call`. Live-verified: 2 facts established, persisted, and present in the next
  turn's prompt. Supersession is deliberately **not** exposed as an inline GM tag — see
  the handoff entry.)*
- **P2.3** End-of-session sweep on the utility tier as the backstop for P2.2 — the GM
  forgetting to tag is the one failure mode inline extraction has. Local model, so free.
  *(Done 2026-08-12. `src/dndc/memory/sweep.py` + `gm/prompts/sweep.md`, run from
  `_cmd_play` after the GM backend closes; `--no-sweep` opts out. Four structural guards
  rather than prompt instructions: scope forced to `player_known` in code, `gm_only`
  never sent to the local model, every proposal grounded against its own transcript
  chunk, and the table confirms before anything is filed. Declines are logged with
  `confirmed: false` and never enter the ledger. D-008 amended first — `canon_write`
  gains `source` and `confirmed`.)*
- **P2.4** `[[GAIN: ...]]` / `[[LOSE: ...]]` → `inventory_change` events → engine mutates
  the sheet, with player/CLI confirmation. Rejected proposals are logged too.
  *(Done 2026-08-13. `gm/inventorytag.py` parses, `rules/inventory.py` performs,
  `game/inventory.py` owns the sheets and the log, the CLI confirms per turn. The parser
  drops what it cannot read cleanly — the `[[CHECK]]` posture, not `[[CANON]]`'s, because
  a guessed item change writes fiction into state. D-008 amended first: the wire format,
  and `inventory_change.applied` for when the table says yes and the sheet cannot comply.
  `/inventory` added, since the GM is now told it does not know what anyone carries.)*
- **P2.5** Chronicle layer: compression job on the utility tier writing `chronicle_write`
  events; prompt builder consumes ledger + chronicle + window.
  *(Done 2026-08-14. `gm/chronicle.py` is the value type + `chronicle.yaml`,
  `memory/chronicle.py` the job, run from `_cmd_play` after the sweep; `--no-chronicle`
  opts out. One entry per session, folding into one when the chronicle outgrows eight —
  without the fold the prompt grows a paragraph per session forever, which is the thing
  D-002's prompt rule exists to prevent. The sweep's grounding check moved to
  `memory/grounding.py` and guards this too: a summary naming someone the session never
  did is retried once, then skipped, because no entry beats a fabricated one. **No
  confirmation gate** — see the handoff; it is not canon and cannot become canon.
  Rendered into the prompt as recollection, explicitly subordinate to the ledger.)*
- **P2.6** Drift test: replay the archived Ashmill and Salt Road logs, extract canon,
  assert the established world survives into a second session. Fixtures live at
  `\\TRUENAS\shared\data\dnd-campaign-logs\` (`logs/` is gitignored).
  *(Done 2026-08-14. `src/dndc/analysis/` — `replay.py` rebuilds a session from its log,
  `drift.py` measures it, `dndc drift LOG...` runs it. Two halves: survival is
  deterministic and asserted through the real prompt builder; contradiction is judged on
  the batch seat, only for facts the passage touches, and every claim must quote the
  passage verbatim. The archived logs carry no canon tags at all — they predate P2.2 — so
  the world is recovered by the sweep, which is what makes them the before-picture.
  **243 facts recovered over 43 turns, 243 survived, 0 lost; 0 contradictions in 373
  checks.** Judge validated by positive control: 3/3 recall, 0/4 false positives.)*

**Phase 2 complete 2026-08-14.** The memory layers exist and are measured.

## Between phases — the backgrounds + starting-equipment ingest

Scheduled by Fable 2026-08-14, ahead of Phase 3: combat is where weightless gear and
skill-short sheets stop being cosmetic.

*(Done 2026-08-15. Backgrounds are an SRD type now — ingested, validated, and granted by
`build_character` (skills, tools, starting kit), with a class pick that duplicates a
granted skill refused back to the GM. Starting equipment resolves through the repository,
so items carry the SRD's names and weights instead of raw indices at 0 lb. P2.4's
0.0-weight gap closed the same way: `apply_gain` takes an optional catalogue, and the
store backs it with the repository. **The SRD contains exactly one background — Acolyte**;
the rest are PHB and outside D-007's licence, so the mechanism is complete and the dataset
is one row. Whether to author original backgrounds as campaign data is a design question,
tagged `FOR DESIGN:` in the handoff.)*

## Between phases — the drift baseline ("the fixture, not the seed")

Ruled by Fable 2026-08-14, implemented 2026-08-15.

*(Recovered canon is now a committed artifact: `data/drift/*.baseline.yaml`, one per
archived session, carrying the facts plus provenance — model, temperature, seed, date,
`dndc` version, commit, and the SHA-256 of the source log so a fixture knows when its log
changed underneath it. `src/dndc/analysis/baseline.py` owns the type;
`dndc drift check | record | measure` are the three operations.

**Survival now needs no model, no NAS and no logs** — it loads a file and renders it
through the real prompt builder, so it is a test (`test_the_committed_baselines_all
_survive`) rather than an errand. Recovery stability is split out as its own number:
re-sweep the log and diff against the fixture, reporting identical / reworded / missed /
new. A seed was added to the Ollama adapter as a tightener per the ruling, never a
substitute — and the live numbers show exactly why. See the handoff.)*

## Phase 3 — Combat

Initiative tracker, action economy, monster stat blocks from SRD, deterministic
resolution with GM narration layered per round; encounter builder (CR budget). Rich
combat CLI view.

**The phase D-001 was written for.** Every number in a fight is the engine's: initiative,
hits, damage, HP, death saves. The GM narrates outcomes it is handed and never computes
one. OD-11/OD-12 apply at their strictest here — the GM receives severity bands, the
interface renders the numbers from state.

Task breakdown:

- **P3.1** Deterministic combat core: combatants, initiative with reproducible
  tie-breaking, the round/turn state machine, action economy (action / bonus / reaction /
  movement), damage application with resistance-vulnerability-immunity, unconsciousness,
  death saves, massive damage. Pure functions and a state machine; **no model, no
  logging** — so the test suite is the whole verification.
  *(Done 2026-08-15. `src/dndc/rules/combat.py`. Combatants are frozen and every change
  returns a new one, so a fight is a sequence of states rather than a mutated object;
  `Encounter` is the one mutable thing and `replace_combatant` is its single choke point.
  Initiative ties break on dexterity → side → name, never on a re-roll, because a fight
  that cannot be replayed is not evidence. Monsters drop at 0 and characters go
  unconscious and roll death saves — a dying character still gets their turn, since that
  turn is where the save happens. 53 tests including a whole-fight replay.)*
- **P3.2** Monster instantiation from SRD stat blocks: a `Monster` becomes combatants with
  rolled or average HP, its actions become usable attacks, multiattack understood.
  *(Done 2026-08-15. `src/dndc/rules/statblock.py` — `from_monster` and `from_sheet`,
  still pure. The SRD is prose in two places and both refuse to guess: **27 of 68
  multiattacks resolve, 41 stay unresolved** carrying their text, because one offering a
  choice would make the engine pick the monster's tactics; and the four
  "…from nonmagical weapons" damage modifiers are recorded but **not applied**, since
  granting them blindly roughly doubles a monster's effective HP. Whole-dataset invariants
  are tested across all 245. Combatants gained `condition_immunities` — an earlier draft
  wrote them into `conditions`, which marks a monster immune to being knocked prone as
  lying on the floor.)*
- **P3.3** Combat event vocabulary — **doc-first per D-008**, and deliberately not
  designed before P3.1/P3.2 exist: guessing what a fight emits before one runs is how a
  vocabulary ends up describing the code instead of the game. An attack is probably a
  `rules_resolution`; round boundaries, initiative order and HP changes are probably not.
  *(Done 2026-08-15. D-008 amended first, items 9–12: `combat_start`, `combat_turn`,
  `hit_point_change`, `combat_end`. **Attacks, damage rolls, death saves and initiative
  added no family** — `rules_resolution.kind` named them in the original 2026-07-27
  ruling, so combat reuses the vocabulary rather than growing it, and which fight a roll
  belongs to rides in the documented `detail` bag. `condition_change` deliberately not
  added: nothing emits it. `game/combatlog.py` is the recorder, and the way the amendment
  was checked — a real fight is played, logged, and read back without re-simulating.)*
- **P3.4** The combat turn loop: engine resolves, GM narrates per round, players act
  through the CLI. Where D-001's boundary takes its real load.
  *(Done 2026-08-15. `game/combatturn.py` + `gm/prompts/combat.md`, driven by a demo
  runner `dndc combat --monster wolf*2`. Resolve → log → narrate, in that order, so a
  narration cannot change an outcome and a lost GM mid-fight still leaves a correct combat
  log. The GM receives **severity words only** (OD-12), measured against the target's own
  maximum. Monster tactics are deterministic — a model choosing targets would make a fight
  unreplayable, which is a live design question flagged in the handoff. An unresolved
  multiattack uses its stated count and **says it approximated**; never silently one.
  Live-verified.)*
- **P3.5** Encounter builder on a CR/XP budget, drawing on the ingested monsters.
  *(Done 2026-08-15. `rules/encounter.py`, driven by `dndc combat --difficulty deadly`.
  **The SRD has no encounter tables** — XP thresholds by level and the group multiplier are
  DMG, outside D-007 — so the budget is ours, and it was **measured against the combat
  engine** rather than asserted: the simulator runs thousands of mechanics-only fights and
  reports win, down and death rates. That caught two real errors — filling greedily from
  the biggest monster prices encounters *backwards*, and a swarm needs a much steeper
  group multiplier than XP suggests. Bands are monotonic for four-character parties and
  provisional for two; the numbers and the simulator's limits are in the handoff.)*
- **P3.6** Rich combat CLI view: initiative order, HP bars, conditions, whose turn it is —
  the authoritative numeric display (OD-11).
  *(Done 2026-08-15. `render_encounter` / `hp_bar` / `choose` / `player_turn` in
  `game/cli.py`. Players pick weapon and target; `--auto` keeps a fight scriptable. Real
  weapons come off the sheet — `weapons_for` derives ability from the weapon's own
  properties, proficiency from what the character is trained in, damage from the SRD
  entry — which is what makes inventory being state (P2.4) pay off. Live-verified.)*

- **P3.7** Monster tactics become the GM's, per the 2026-08-15 (c) ruling: a `[[TARGET:]]`
  declaration in the narration call it already makes, engine resolves it, deterministic
  policy as the logged fallback.
  *(Done 2026-08-15 (j). `gm/targettag.py` + `combatturn.resolve_target`. D-008 amended
  first: the wire format, and `combat_turn` gains `target` / `target_source`
  (`declared` | `policy` | `stale`). Declared a turn ahead, so it costs no extra call —
  and a declaration overtaken by events is reported `stale` rather than silently replaced,
  because "the GM chose badly" and "the GM's choice expired" are different findings.
  Live-verified: the GM had a wounded wolf turn on whoever hurt it.)*

**Phase 3 complete 2026-08-15.** Combat exists end to end: a deterministic core, SRD stat
blocks, a logged event vocabulary, a turn loop with the GM narrating outcomes it never
computed, an encounter budget measured against the engine, and a view that owns the
numbers.

## Between phases — original backgrounds (the 2026-08-15 (c) ruling)

Ruled by Fable 2026-08-15 (c), option 3, ahead of Phase 4: co-creation proposes an
original background, the engine validates the shape deterministically, the table confirms,
confirmed ones persist as campaign data. The SRD's one row (Acolyte) is untouched.

*(Done 2026-09-02. D-008 amended first — items 15 and 16: the `[[BACKGROUND:]]` wire
format, and a `background_write` family carrying `confirmed` and `applied`, so a
background the table refused is a measurement rather than a silence. `gm/backgroundtag.py`
parses, `rules/background.py` decides what may be granted, `schema/campaign.py` holds the
`CampaignBackground` type and the `backgrounds.yaml` book, and `CreationSession` asks the
table before anything is filed. **The shape rules are the ruling's**: exactly two skills
from the standard list, at most one tool **or** one language, never a numeric bonus, and no
equipment — starting gear stays in `[[PROPOSE:]]` where the SRD catalogue can check it.

The class-pick clash needed nothing new: `build_character` has refused a class skill the
background grants since the ingest task, and campaign backgrounds reach that check by the
same path SRD ones do — which is the whole reason `CampaignBackground` subclasses the SRD
type instead of paralleling it. Two things fell out: a background's `language:` names the
language and the character simply speaks it (a grant with a choice left in it is a grant
that gets left half-spent), and expertise may now land on a background skill, which 5e
always allowed and the engine was refusing. `dndc sheet validate` gained `--campaign`,
without which it silently stops checking half of a character's proficiencies.

Live-verified: from one sentence of concept the GM wrote *Coast-Road Grifter* — deception,
sleight of hand, a forgery kit, and a feature about being known on the road — and chose the
rogue's four skills around it. **Kelly holds content veto**; the sample is in the handoff.)*

## Phase 4 — NPC agent tier (D-003)

NPC schema (voice card, knowledge scope, canon-ledger view), per-turn prompt rebuild
by GM director, gatekeeper pass, stance-scoped supersession port. Routing layer picks
Ollama endpoint (toto-llm primary, sam-pc secondary) from config.

**The phase D-003 was written for, and the one the canon scopes have been waiting for since
P1.2.** Two properties govern every task below, both ported from the mystery:

- **Substitution, never prohibition.** An NPC's prompt is built from what that NPC knows.
  There is no "do not mention the tunnel" line anywhere, because that is the pink-elephant
  anti-pattern — protection comes from what is *absent* from the prompt. `gm_only` canon is
  never assembled into an NPC call at all, which makes the guarantee testable rather than
  hopeful.
- **The gatekeeper is a backstop, not the gate.** It fails *open*: a broken checker must
  never break a turn, because the architecture is what protects and the checker only
  measures how well. Raw drafts are kept whatever the verdict — pre-censor drafts are the
  denominator of every leak rate Phase 7 will want.

Task breakdown:

- **P4.1** NPC records as campaign data: the voice card (who they are, how they talk), the
  knowledge scope (what canon they may see), and the ledger's per-NPC view. `npcs.yaml`
  beside `canon.yaml`, hand-authorable; `dndc npc list|show`. No model calls, no prompt
  assembly — the shape is the commitment.
  *(Done 2026-09-02. `schema/npc.py` — `VoiceCard`, `NPC`, `NPCBook`; `CanonLedger.for_npc`
  is the filter and `npc_issues` is the authoring lint. **An NPC sees only what it was
  granted**: entries carrying one of its `knows_tags`, entries named in `knows`, campaign
  common knowledge, and its own beliefs. Three exclusions are *unconditional* and cannot be
  overridden by authoring — `gm_only`, `player_known`, and any other character's beliefs.
  `player_known` is the one that changed during the work: it started as reachable-by-tag and
  a test caught the leak, because **the sweep writes that scope automatically** (P2.3), so it
  is the one bucket that fills with everything the party did without anyone authoring it.
  `NPC.notes` exists for what the model must not be told and is never rendered.)*
- **P4.2** NPC prompt assembly: voice card + permitted canon + their own beliefs + what
  they have already said, in an order that is data rather than code (section order vs.
  leak rate is a research variable). Pure function; the absence property is asserted here.
  *(Done 2026-09-02. `gm/npcprompt.py` + `gm/prompts/npc_core.md`. **The builder takes a
  ledger, never a list of entries** — it calls `for_npc` itself, so the filter cannot be
  forgotten or bypassed by a caller in a hurry; the one door into an NPC prompt is the one
  with the lock on it. Facts and beliefs render under separate headings, because a model
  that treats them alike turns a private suspicion into something "everyone knows". The
  absence property is asserted on the assembled bytes rather than on the filter, and one
  test greps the whole prompt for prohibition phrasing — "do not mention" appearing anywhere
  would mean the design had quietly inverted. Landed with P4.1 because neither half is
  testable alone: the guarantee is a property of the assembled call.)*
- **P4.3** The routing layer and the NPC seat: pick an endpoint from `ollama_endpoints`
  (toto-llm primary, sam-pc registered since day one per OD-5), health-check and fall back,
  emit `npc_turn` with `CallStatus`/`call_id`. First task in the phase that needs the LAN.
  *(Done 2026-09-02. `models/routing.py` — an endpoint is a candidate only if it is up
  **and has the model**, because a host that answers without the model fails at generate
  time, halfway into a scene; nothing ever substitutes a different model, which would make
  every later measurement a lie. Resolution is cached (`force=True` re-probes after a
  failure, not before every call that might have one). `game/npcturn.py` runs a turn and
  keeps the claims ledger automatically. D-008 amended first, items 17–18: `knowledge_scope`
  carries the permitted entry **ids**, and `npc_turn` gains `endpoint`. `dndc npc speak` is
  the demo runner. **Live-verified on toto-llm — and the number worth knowing is that a
  cold 70B costs ~68 s on the first call and ~1–3 s warm.**)*
- **P4.4** The gatekeeper pass: check a draft against what that NPC was permitted to know
  and against established canon; `pass | revised | blocked`, minimal rewrite, fail open,
  raw draft logged. Validated by **positive control** before any zero is believed — the
  P2.6 discipline: plant leaks, prove the checker catches them.
  *(Done 2026-09-02 (d). `gm/gatekeeper.py` + `gm/prompts/gatekeeper.md`, wired into
  `NPCVoice` as an optional gate. D-008 amended first, items 19–20: the verdict vocabulary
  gains **`unchecked`** — fail-open must be visible, or a night when the checker was down
  reads later as a night with no leaks — and `npc_turn.draft` keeps the pre-gate text when
  the gate changed it. **The checker is never told the secret either**, which is where this
  departs from the mystery deliberately: the NPC prompt never held `gm_only` canon, so a
  leak can only be invention, and asking about invention catches it without the plot
  entering a second model call that untrusted draft text could prompt-inject.
  `dndc npc control` runs planted cases and scores recall and false positives — the P2.6
  rule, that a zero is also what a broken instrument produces. **The control immediately
  earned itself**: see the handoff for the miss it found, the false positive it found after
  that, and the seat it settled by measurement.)*
- **P4.5** Wiring into the turn loop: the GM directs who speaks (a tag, the eighth use of
  the convention), the engine runs that NPC's own call, the gatekeeper gates it, and what
  the NPC said comes back to the GM as established dialogue. Cost and latency at the table
  are the thing to measure here.
  *(Done 2026-09-02 (f). `gm/speaktag.py` + the `[[SPEAK:]]` section in `system_core.md`;
  D-008 amended first, items 21-23. **The line comes back as engine input, never in the
  assistant slot** — dialogue rides one turn forward into the following user message, so a
  GM can read what a character said and can never read it back as something it wrote. A GM
  that learns to write Maren's lines is a GM holding `gm_only` canon speaking with her
  mouth, which is the leak the tier exists to stop, so the protection is structural rather
  than a standing instruction. `NPCVoice.warm_up()` pays the cold load at session start —
  **62 s cold, 0.3-0.6 s warm, measured** — and `cost.latency_ms` now records what every
  backend has always measured and thrown away. Live-verified: the gate caught an invented
  quay watch mid-scene, and the run found a **leak vector of its own** — see the handoff.)*
- **P4.6** Stance-scoped supersession (mystery OD-13): when the GM changes what an NPC
  knows or believes, the change is *decisive* in the next prompt rather than a quiet
  contradiction of everything the window still remembers them saying.
  *(Done 2026-09-03. `[[BELIEF: <name> | <what they now believe>]]` — the ninth tag and the
  second that costs a second call — declares a **change of mind**, distinct from
  `[[CANON: npc_belief]]` which adds one; the direction is not guessable from the sentence,
  so it is declared (`[[GAIN/LOSE]]` precedent). A judge on the gate's seat weighs every
  standing belief against the new one, each retirement is superseded through the ledger
  with `source: stance`, and the pass runs **before** anyone speaks so a character turned
  around in the same reply answers from the new mind. Fails open by retiring nothing; a
  `belief_change` row keeps "ran and retired nothing" distinct from "never ran".
  **Control: 4/4 retired, 0/13 in error**, stable over six runs — but it took four prompt
  revisions and then a **structural** fix that four revisions could not manage: every
  retirement must **quote the words it contradicts**, and an unquoted one is dropped. The
  control also caught the author again, not the judge. Live: the pass works end to end on
  the 70B in ~4 s, **but the GM did not emit the tag once in nine turns of designed
  pressure** — see the handoff, it is the open question.)*
- **P4.7** Live verification and a scene at the table: a planted-leak control against the
  real 70B seat, then NPCs in actual play, findings to `docs/playtests/`.
  *(Done 2026-09-02 (g), except the humans — findings in
  `docs/playtests/2026-09-02-npc-tier-verification.md`. The cast was **recovered from
  session 1's log rather than invented**, and the planted leaks are the campaign's own
  secrets: two of them leak player-character canon Kelly and Sam wrote at co-creation,
  which is the leak that would actually matter at this table. **6/6 caught, 0/7 false
  positives, three consecutive runs** — after the control caught the gate out twice, once
  on a secret dressed as an impression ("you've got the look of a man who's run a con
  before") and once on the checker knowing what a character knows but not who he is. The
  scope held visibly in play: the caravan master, two facts to the guard's eight, asked
  *"What are you talking about, a crate?"*. **A turn where somebody speaks costs ~15 s**,
  three times what (f) implied. An evening with Kelly and Sam is the part still
  outstanding.)*

## Phase 5 — Campaign persistence + between-session jobs

Save/load full campaign state; `seq` continuity across process restarts (npc-village
rider); recap generation ("previously on…") on utility tier; session cost report.

**What already survives a session, and what does not.** The ledger is in `canon.yaml`, the
sheets in `characters/`, the chronicle in `chronicle.yaml`, and each is written as it
changes. What is lost at the end of every session is the part nobody thought to name:
*where the party is standing*. The scene, the turn window, whose seat it is. This phase
closes that hole and then makes the between-session jobs read the log rather than the room.

One rule governs the phase: **a save point stores only what nothing else owns.** Canon,
sheets, backgrounds and chronicle already have files and already have writers; copying
them into a save would create a second authority, and two authorities for one fact drift
the first time one path writes and the other does not.

Task breakdown:

- **P5.1** The save point: scene, turn window (with the dialogue that rode with it), the
  acting player, and the session lineage, written atomically after every turn and closed
  at session end. `dndc play --campaign SLUG` resumes it; `--fresh` ignores it. No model
  calls.
  *(Done 2026-09-03 (b). `schema/save.py` + `game/saves.py`; D-008 amended first, item 27
  — `session_meta.resumed_from` / `resumed_turns`, a field rather than a family, because
  resuming is a fact about how a session **started** and not an event inside it. The save
  emits nothing: it is state, and it is the one file in the project that is rewritten
  rather than appended to, which is exactly why it holds nothing the log is the record of.
  **`closed` is the whole design.** An open save is a crash — the window comes back whole
  and the run continues the same log, so `seq` carries on and the evening is one record
  instead of two halves. A closed save is a bedtime — the scene comes back and the turns
  do **not**, because D-002 says a past session reaches the prompt as chronicle prose and
  replaying the turns the chronicle summarises is the growing-transcript failure the three
  layers exist to prevent. Live-verified end to end on the API seat, including a session
  killed mid-scene: one log, `seq` 0→14 unbroken across the restart, a second
  `session_meta` at seq 6 naming its own resume and its own seed, and the GM's next reply
  continuing the ford scene a dead process had written. Found and fixed on the way: two
  runs starting in the same second shared a log file, which after this task would read as
  a session that had inexplicably restarted.)*
- **P5.2** `seq` continuity across process restarts, made real by P5.1's lineage: an open
  save reopens *its own* log and the counter continues where it stopped, so a crash
  mid-evening leaves one session record rather than two halves. `session_meta` says it was
  resumed.
- **P5.3** Recap on the utility tier: "previously on…" generated from the chronicle and the
  session's own canon, printed when a campaign is picked up again. Read-only over the
  record — a recap that could write canon would be a fourth memory layer nobody ratified.
- **P5.4** Session cost report: per-seat totals, call counts and latency read back from the
  log's `cost` rows, printed at session end and available as `dndc cost`. The seat split
  (Fable, 2026-08-14) was made to be measurable; this is the thing that measures it.

## Phase 6 — LAN web GUI

FastAPI backend over the same engine; two-device play from the couch; hot-seat CLI
remains supported.

## Phase 7 — Research instrumentation

Canon-drift metrics, ruling-fairness analysis over `gm_adjudication`, NPC
knowledge-leak detection, cost-per-session dashboards; analysis scripts in
`analysis/`.
