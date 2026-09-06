# CLAUDE.md — D&D Campaign Companion

## What this project is

A Claude-GM'd D&D 5e campaign engine for two at-home players (Kelly and Sam), built
CLI-first with a LAN web GUI planned. It doubles as a research instrument: every session
emits structured logs for studying long-horizon GM consistency, canon drift, and NPC
knowledge leakage — the longest-horizon consistency instrument in this household's
portfolio (llm-murder-mystery, npc-village).

**Read `docs/DESIGN-DECISIONS.md` before making architectural changes.** It contains
the ratified decisions (D-001…D-008) with rationale, plus the OD register mirroring
`race-control/docs/planning/active/2026-07-27-dnd-campaign-companion.md`. Do not
contradict a ratified decision without flagging it explicitly. `docs/TASKS.md` is the
phased build plan; work through it in order unless directed otherwise.

## Architecture in one paragraph

A **deterministic rules core** (no LLM) owns all mechanics: dice, combat resolution,
initiative, sheets, slots, HP, inventory — SRD 5e data ingested as structured files.
A **GM brain** (Claude, behind a `GMBackend` interface with `api` and `subscription`
adapters) narrates, adjudicates creative actions, directs plot, and gates NPC
knowledge; it narrates mechanical outcomes handed to it by the rules engine and never
invents them. **NPC voices** are local ~70B agents (suspect pattern from the mystery:
knowledge scopes, claims-ledger entries, voice cards, director-gated output). A
**utility tier** (8–12B local) does recaps, memory compression, and SRD RAG. Campaign
continuity uses a three-layer memory ported from npc-village: session log → **canon
ledger** → campaign chronicle. Everything is logged as an append-only JSONL event
stream with per-turn cost telemetry.

## Model seats

- **GM:** Claude via `GMBackend` — `api` adapter (Anthropic SDK + key from `.env`) or
  `subscription` adapter (Agent SDK / headless CC under Max login). Session-start
  toggle, sticky default (D-004). Sonnet-class default; Opus escalation at authored
  threshold moments (OD-3).
- **NPCs:** local llama3.3:70b via Ollama on toto-llm (`192.168.50.11:11434`).
- **Utility:** 8–12B via Ollama; second endpoint on Sam's PC (`192.168.50.161`)
  registered in config from day one, used from Phase 4.
- All endpoints/models live in `config.yaml` — never hardcode a model name or URL.
  "All-local" mode (local model in the GM seat) must remain runnable for free tests.

## Repo layout (target)

```
docs/                  DESIGN-DECISIONS.md, TASKS.md, PROGRESS.md,
                       LAN-ACCESS.md (what serving exposes), playtests/
data/srd/              ingested SRD 5e structured data + LICENSE/attribution
campaigns/             campaign + save state (data, not code; path from
                       config `campaigns.dir` / $DNDC_CAMPAIGNS_DIR)
src/dndc/
  models/              GMBackend (api, subscription adapters), ollama adapter, seats
  schema/              pydantic types: sheets, monsters, spells, canon entries, events
  rules/               dice, checks, combat resolution, initiative — pure functions
  srd/                 SRD ingestion, validation, repository (added P0.2, ratified)
  gm/                  prompt assembly, canon ledger, NPC gating, threshold escalation
  memory/              session log / canon ledger / chronicle layers, compression jobs
  game/                turn loop (`evening.py`), session construction (`setup.py`,
                       console-free), character co-creation flow, CLI (rich)
  logging/             JSONL event emitter + cost telemetry
analysis/              scripts/notebooks over logs
logs/                  gitignored; JSONL session logs
tests/
```

## Conventions

- Python 3.11+, `pydantic` for schema, `pyyaml` for config/campaign files, `rich` for
  CLI. Minimal dependencies; ask before adding heavyweight ones.
- Rules engine = small pure functions (state in, events out); unit-testable with zero
  model calls. Model calls mockable; tests never need network/GPU.
- Campaign content is **data**. If a story change requires code, fix the schema.
- SRD data is CC-BY-4.0 — keep the attribution file with the data. Original campaign
  content only; never ingest published adventure modules.
- Prompts are templates in `src/dndc/gm/prompts/`, not inline strings. Significant
  prompt changes are design-relevant: note them in PROGRESS.md.
- Logging is append-only JSONL; never mutate a written log. Event vocabulary is
  specified in DESIGN-DECISIONS.md D-008 — extend it there first, then in code.
- Stamp the commit SHA into `session_meta` (lesson from the mystery).

## Session protocol (mandatory — this is the whole communication channel)

Kelly does not copy-paste between Claude sessions. The docs are the channel.

**Session start (`/pickup` or do this unprompted):** read `docs/PROGRESS.md` **from the
top** (the Open Decisions block lives at the head of the file — a tail read will miss
it), apply any new Fable rulings before touching code, then read the latest handoff
entry and TASKS.md for the current task.

**Session end (`/handoff` or do this unprompted):** append a dated entry to
PROGRESS.md — task IDs completed, deviations and why, known issues, recommended next
task — and tag anything needing a design ruling with a literal **`FOR DESIGN:`**
prefix so Fable can grep for it. Work is not "done" until this entry exists.
**Entry dates come from the system clock (e.g. `date` / `Get-Date`), never from
inference — multiple sessions on one day get (b), (c)… suffixes, not incremented
dates.** Verified provenance is the point of a dated log. End the
session message with an ADHD-friendly **TLDR** telling Kelly (1) what is needed from her
and (2) whether the next session is blocked pending Fable's review — name the OD number.

**Rulings take effect only once recorded in the repo docs** — chat is not ratification.
One session, one commit; no code edits under a live play session.

If a session finishes a phase that has a plan doc in race-control `planning/active/`,
follow the race-control workflow: update that doc's status header + Implementation
Notes (see `race-control/docs/planning/_workflow.md`).

## Documentation (Single Source of Truth)

Infrastructure docs live in race-control/docs/ (mirrored to \\TRUENAS\shared\lab-docs, the LAN read surface).
- Hardware inventory: docs/inventory/hardware.md
- Network map: docs/inventory/network.md
- Services: docs/inventory/software-services.md
- All projects: docs/project-index.md
- Doc lifecycle & strategy: docs/planning/_workflow.md

For this PC, paths are direct: `C:\dev\race-control\docs\`

If during this session you discover something about our hardware, network, services,
or cross-project capabilities that isn't already in the central docs and would be
useful context for future sessions or for the humans (Kelly & Sam), flag it — it
likely belongs in the central docs above.

## Current state

- Design complete: D-001…D-008 ratified 2026-07-27 (authored with Claude Fable 5 in
  the Claude.ai project space). Phase plan tracked in
  `race-control/docs/planning/active/2026-07-27-dnd-campaign-companion.md`.
- No code exists yet. Next action: TASKS.md Phase 0 (P0.1 onward).
- Before Phase 1 GM work: Kelly must place an API key in `.env` (console spend cap
  set). The `subscription` adapter can be built + tested with her existing CC login.
