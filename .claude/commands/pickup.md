Session pickup for the dnd-campaign repo. Do these in order before touching code:

1. Read docs/PROGRESS.md FROM THE TOP. The "Open decisions for Fable" block is at the
   head of the file — a tail read will miss it. If there are newly Ruled items not yet
   implemented, they take priority over TASKS.md order.
2. Read the most recent handoff entry in PROGRESS.md (top dated entry).
3. Grep the repo docs for `FOR DESIGN:` — do not attempt to resolve those yourself;
   they are awaiting a Fable ruling. Work around them.
4. Read docs/TASKS.md and confirm the recommended next task from the handoff entry.
5. State a short plan for this session, then begin.

Constraints reminder: never contradict a ratified decision in docs/DESIGN-DECISIONS.md
without flagging it; models/endpoints come from config.yaml only; one session, one
commit.
