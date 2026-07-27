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

**None.** D-001…D-008 / OD-1…OD-6 ratified 2026-07-27 (see DESIGN-DECISIONS.md).

### Protocol in effect (Fable, 2026-07-27)

- **The docs are the channel.** No copy-paste through Kelly. Session start: read this
  file from the top, apply new rulings before code. Session end: dated handoff entry,
  `FOR DESIGN:` tags for anything needing a ruling. Work isn't done until the entry
  exists.
- **A Fable ruling takes effect only once recorded in the repo.**
- **One session, one commit. No code edits under a live play session.**

### Ruled — awaiting implementation

- All of D-001…D-008 (initial architecture). Implementation = Phases 0–7 per TASKS.md.

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
