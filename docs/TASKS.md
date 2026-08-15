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
  *(Done 2026-08-15. `src/dndc/analysis/` — `replay.py` rebuilds a session from its log,
  `drift.py` measures it, `dndc drift LOG...` runs it. Two halves: survival is
  deterministic and asserted through the real prompt builder; contradiction is judged on
  the batch seat, only for facts the passage touches, and every claim must quote the
  passage verbatim. The archived logs carry no canon tags at all — they predate P2.2 — so
  the world is recovered by the sweep, which is what makes them the before-picture.
  **243 facts recovered over 43 turns, 243 survived, 0 lost; 0 contradictions in 373
  checks.** Judge validated by positive control: 3/3 recall, 0/4 false positives.)*

**Phase 2 complete 2026-08-15.** The memory layers exist and are measured.

## Between phases — the backgrounds + starting-equipment ingest

Scheduled by Fable 2026-08-14, ahead of Phase 3: combat is where weightless gear and
skill-short sheets stop being cosmetic.

*(Done 2026-08-16. Backgrounds are an SRD type now — ingested, validated, and granted by
`build_character` (skills, tools, starting kit), with a class pick that duplicates a
granted skill refused back to the GM. Starting equipment resolves through the repository,
so items carry the SRD's names and weights instead of raw indices at 0 lb. P2.4's
0.0-weight gap closed the same way: `apply_gain` takes an optional catalogue, and the
store backs it with the repository. **The SRD contains exactly one background — Acolyte**;
the rest are PHB and outside D-007's licence, so the mechanism is complete and the dataset
is one row. Whether to author original backgrounds as campaign data is a design question,
tagged `FOR DESIGN:` in the handoff.)*

## Between phases — the drift baseline ("the fixture, not the seed")

Ruled by Fable 2026-08-15, implemented 2026-08-17.

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
  *(Done 2026-08-18. `src/dndc/rules/combat.py`. Combatants are frozen and every change
  returns a new one, so a fight is a sequence of states rather than a mutated object;
  `Encounter` is the one mutable thing and `replace_combatant` is its single choke point.
  Initiative ties break on dexterity → side → name, never on a re-roll, because a fight
  that cannot be replayed is not evidence. Monsters drop at 0 and characters go
  unconscious and roll death saves — a dying character still gets their turn, since that
  turn is where the save happens. 53 tests including a whole-fight replay.)*
- **P3.2** Monster instantiation from SRD stat blocks: a `Monster` becomes combatants with
  rolled or average HP, its actions become usable attacks, multiattack understood.
  *(Done 2026-08-19. `src/dndc/rules/statblock.py` — `from_monster` and `from_sheet`,
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
  *(Done 2026-08-20. D-008 amended first, items 9–12: `combat_start`, `combat_turn`,
  `hit_point_change`, `combat_end`. **Attacks, damage rolls, death saves and initiative
  added no family** — `rules_resolution.kind` named them in the original 2026-07-27
  ruling, so combat reuses the vocabulary rather than growing it, and which fight a roll
  belongs to rides in the documented `detail` bag. `condition_change` deliberately not
  added: nothing emits it. `game/combatlog.py` is the recorder, and the way the amendment
  was checked — a real fight is played, logged, and read back without re-simulating.)*
- **P3.4** The combat turn loop: engine resolves, GM narrates per round, players act
  through the CLI. Where D-001's boundary takes its real load.
- **P3.5** Encounter builder on a CR/XP budget, drawing on the ingested monsters.
- **P3.6** Rich combat CLI view: initiative order, HP bars, conditions, whose turn it is —
  the authoritative numeric display (OD-11).

## Phase 4 — NPC agent tier (D-003)

NPC schema (voice card, knowledge scope, canon-ledger view), per-turn prompt rebuild
by GM director, gatekeeper pass, stance-scoped supersession port. Routing layer picks
Ollama endpoint (toto-llm primary, sam-pc secondary) from config.

## Phase 5 — Campaign persistence + between-session jobs

Save/load full campaign state; `seq` continuity across process restarts (npc-village
rider); recap generation ("previously on…") on utility tier; session cost report.

## Phase 6 — LAN web GUI

FastAPI backend over the same engine; two-device play from the couch; hot-seat CLI
remains supported.

## Phase 7 — Research instrumentation

Canon-drift metrics, ruling-fairness analysis over `gm_adjudication`, NPC
knowledge-leak detection, cost-per-session dashboards; analysis scripts in
`analysis/`.
