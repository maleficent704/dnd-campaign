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
amended D-006. The archived Ashmill log (TrueNAS) is the before-picture fixture for
the drift test.**

## Phase 3 — Combat

Initiative tracker, action economy, monster stat blocks from SRD, deterministic
resolution with GM narration layered per round; encounter builder (CR budget). Rich
combat CLI view.

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
