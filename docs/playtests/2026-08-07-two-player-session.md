# Playtest — The Salt Road, session 1 (two players)

**Date:** 2026-08-07 · **Players:** Kelly (Corin Vale), Sam (Brother Hammond)
**Billing:** subscription (Max) · **Commit:** `7e87775` (dirty worktree)
**Logs:** `logs/20260807-172707.jsonl` (Sam's co-creation), `logs/20260807-174124.jsonl` (play)
**Length:** 13 min creation + 57 min play · **8 player turns**, 14 GM replies, 4 checks
**Would-have-cost:** $1.2765 total — see finding 5, this number does not mean what the
first playtest's number meant.

This is **P1.5 proper**. The solo session on 2026-08-05 covered everything except the one
thing Phase 1 had never run: two people at one keyboard. That part now works.

---

## What happened

Sam built **Brother Hammond** in three exchanges — a big gentle human fighter, ex-member
of a doomsday cult whose prophet turned out to be a con man, now doing good deeds as
penance and sworn never to lie. Four backstory facts went to canon.

Play opened at a caravan waystation on the salt flats: a teamster accused of theft, held
by two guards, a crowd forming. Sam went to look at the accused. Kelly went for the
wagons — spotted that the third sat heavy at the front, failed to read the churned ground,
successfully got a canvas flap open one-handed, then tried to talk her way out of being
caught at it with an invented missing friend. That lie failed, the retry failed harder,
and the guard had a hand on her shoulder when Sam walked Hammond over to stand beside her.
The session ended there, mid-standoff.

---

## Findings

### 1. Hot-seat rotation works; `/switch` did not (fixed 2026-08-09)

The mechanic itself was fine — the GM tracked two characters without confusion, addressed
each player's turn to the right one, and when Hammond arrived it wrote him *arriving*,
with Corin's shoulder still pinned. Nothing bled between them.

The command was the problem. `/switch corin` was rejected — the lookup was an exact
full-name match, so it wanted `/switch corin vale`. At a table you say "Corin". Worse, the
lookup existed **twice**, in `_play_command` and again in the loop, with the same rule
written out both times, which is why the error message and the actual switch could
disagree.

**Fixed:** one `resolve_member()` matching in tiers — full name, then a single name out of
it, then a prefix — stopping at the first tier that hits, so a unique first name is never
made ambiguous by some longer name it prefixes. Player names match too (`/switch sam`),
with character names winning a collision. Ambiguity is reported, never guessed.

### 2. DC anchoring resolved itself — no ladder needed

The first playtest's finding 3 was that all three DCs were 12. This session: **12, 12, 13,
14**. The two 12s were a Perception sweep and a one-handed knot; then the first lie was
13, and the *retry of a lie that had already failed* was 14. That is the correct shape —
the same action is harder once the guard is already suspicious.

Fable pre-authorised a DC ladder in the prompt if anchoring persisted. It did not persist.
**Recommend not adding it** — n=3 was too small, and the GM is pricing situationally.

### 3. Co-creation converged for a second player, first time

Sam came in with "let's think a little more ridiculous" — no concept at all — and had a
finished, legal character in three exchanges. The engine-injected propose-now nudge did
its job on a player who was deliberately not being helpful, which is the case the prompt
alone failed three times running.

Also worth noting: the GM offered Sam four *flavours of ridiculous* rather than four
mechanical options, and he picked one and ran. The interview is doing the thing it was
designed to do.

### 4. Backstory keeps paying off, and it is the only memory there is

Corin's grifter background shaped every turn she took — the invented missing friend is a
grift, and the GM narrated it as one. Hammond's vow never to lie was live in Sam's head
from the first turn even though it never came up mechanically.

That is canon written at co-creation. Nothing written *during* play survives: the
waystation, the accused teamster, the two guards, the heavy third wagon are all gone the
moment the process exits. Same finding as the first playtest, one campaign later. Phase 2.

### 5. Subscription would-have-cost is ~13× api cost — one known cause, one new one

Per GM turn:

| | prompt | cache read | cache write | $/turn |
|---|---|---|---|---|
| api (2026-08-05) | ~2.7k | 2,715, written once | 0 after turn 1 | ~$0.006 |
| subscription (this session) | (not reported) | ~28,000 | **8,900–11,100 every turn** | ~$0.08 |

Two separate effects, and only the first is old news.

**Known (OD-10, ruled 2026-08-04):** headless Claude Code wraps our GM prompt in its own
harness — ~33–40k tokens of system prompt and tool definitions riding along every
invocation. That is why the read column says 28k where `api` says 2.7k, and it is exactly
why OD-10 made `api` the sticky default for play sessions.

**New:** subscription mode writes 8,900–11,100 cache tokens on **every turn**. The `api`
adapter writes once, on turn 1, and reads thereafter. A cache that is rewritten each turn
is not doing its job, and unlike the harness overhead this does not look inherent.

Neither costs Kelly anything at point of use — that is what a Max seat is for. But
`would_have_cost` is the number OD-10's band and the research cost model are built on, and
$1.28 for 70 minutes is not comparable to the first session's $0.50 for 81 minutes. The
game got *cheaper* per turn; the meter went up 13×.

Also: `input_tokens` reads **2** on every subscription call — a hole in that adapter's
usage capture, and the reason the cache-write effect was invisible until the log was
summed. Straight bug; no ruling needed.

**FOR DESIGN:** the reporting question is **OD-16** in PROGRESS.md — narrow, and
deliberately not a re-litigation of OD-10.

### 6. Scaffolding is still a formula (unchanged from the first playtest)

Every one of the 14 replies at `high` closed with an options menu. Addressed 2026-08-09 by
OD-15's implementation — `/scaffolding high|low|off` plus a phrasing-variety clause — but
that landed after this session, so this log is a clean before-picture for it too.

---

## Verdict

**Phase 1 is complete.** Every part of the loop has now run under two players: adapters,
prompt assembly, turn loop with engine-routed checks, co-creation, hot seat. The
outstanding work is all Phase 2 (memory) and the cost-telemetry question above.
