Session handoff for the dnd-campaign repo. The session is NOT done until this is
complete:

1. Append a dated entry to docs/PROGRESS.md (below the Open Decisions block, above
   older entries) containing:
   - Task IDs completed (from TASKS.md) and a one-line summary each
   - Deviations from plan and WHY
   - Known issues / loose ends
   - Anything needing a design ruling, each tagged with a literal `FOR DESIGN:` prefix
   - Recommended next task
2. If a design question is a genuine blocker, also add it to the "Open now" list in
   the Open Decisions block at the top of PROGRESS.md.
3. If this session completed a full phase, check whether the race-control planning doc
   (race-control/docs/planning/active/2026-07-27-dnd-campaign-companion.md) needs its
   status log updated per race-control/docs/planning/_workflow.md.
4. Commit (one session, one commit). The pre-commit hook will warn if src/ changed
   without a PROGRESS.md update — that warning means you skipped step 1.
