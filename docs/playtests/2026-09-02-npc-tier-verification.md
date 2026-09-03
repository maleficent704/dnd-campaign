# Playtest — the NPC tier at the Brakewater crossroads (P4.7)

**Date:** 2026-09-02 · **Driver:** Claude Code (no humans at the table — see *What this is
not*) · **Billing:** api · **Commit:** `027a2f3` (dirty worktree)
**Seats:** GM `claude-sonnet-5` · NPCs and gate `llama3.3:70b` on toto-llm
**Logs:** `20260903-032415.jsonl` (the scene), plus ten `npc control` runs
**Scene:** 10 turns, 10 GM calls, 7 NPC calls, 0 dice rolled

The first end-to-end verification of the NPC agent tier (D-003) against a real campaign:
real canon, a real cast, and a scene that picks up exactly where session 1 stopped — the
guard's hand on Corin's shoulder, mid-standoff.

## What this is not

**Kelly and Sam were not at the table.** I played both characters. That makes this a
verification of the machinery and *not* a playtest of the experience: nothing here says
whether the tier is fun, whether a 15-second pause reads as tension or as a hang, or
whether the innkeeper sounded like a person to the people who invented her. Those are the
questions the real session answers, and they are still open.

## Setup, and where it came from

The cast was **recovered from session 1's log, not invented.** `20260807-174124.jsonl`
established Brakewater, the stalled six-wagon caravan, the crate gone from the third wagon,
the guard, the accused teamster, and the caravan master away at the well-house. Nine canon
entries were filed by hand from that log — the P2.3 sweep's job, done manually because
session 1 predates the sweep — and three NPC records written from the GM's own
descriptions.

**None of the three is named**, because the campaign has never named them. `[[SPEAK: the
caravan guard | ...]]` works fine, and a descriptive name is the honest record until the
fiction supplies a real one.

Knowledge scopes, from `dndc npc list`:

| character | facts in scope |
|---|---|
| the caravan guard | 8 |
| the accused teamster | 7 |
| the caravan master | **2** |

The master's 2 is the interesting number. Canon says he has been at the well-house since
the noon stop, so he has no `caravan` tag and **does not know a crate is missing.** That is
not an instruction anywhere; it is what his prompt does not contain.

---

## Findings

### 1. The scope holds, and you can watch it hold

Turn 10, asked whether the crate was ever on the manifest:

> **the caravan master:** *"What are you talking about, a crate? I don't recall any crate
> being listed on my manifest for the third wagon…"*

A character learning something from the party, in the party's presence, because the ledger
says he has not been told. The guard and the teamster, in the same scene, both discussed
the crate freely. That is D-003 working in play rather than in a test, and it is visible in
the log as `knowledge_scope` — 8, 7, and 2 entries on the rows that produced those lines.

*(Borderline, recorded not fixed: "I don't recall any crate on my manifest" does assert a
manifest, which is not in his two facts. A manifest is ordinary business for a caravan
master — the "business of being alive" clause — so the gate passed it and I think it was
right to. Noted because the next one might not be so ordinary.)*

### 2. The gate caught a real invention that would have desynchronised the fiction

Turn 6, the teamster's draft:

> *"I remember Corin Vale was walking around, checking the loads… And one of the other
> teamsters, I think it was Jax, he was nearby too."*

**Corin was not there.** She arrived at dusk; this is the noon stop. The draft invented a
witness (Jax) and placed a player character at a time and place she has never been — which
is worse than a leak, because the GM would have inherited it as established. Revised to
keep his answer and drop both, and the draft is in the log beside it.

### 3. The checker knew what the guard knows and not who he is

Turn 1, the guard's draft said *"My cargo's gone missing, from my wagon"* — and the gate
**revised it away as an invention**, to "A crate's gone missing from one of the wagons."

That phrase is in his own sample lines. His voice card calls him *the man whose wagon the
crate went missing from*. The checker was never shown any of it: `Gatekeeper` assembled the
canon scope and the character's name, and nothing else.

**A character's identity is a source of truth for them**, and a checker holding only the
canon list will keep flattening precisely the details that make a voice sound like a
person — the possessives, the trade, the "not my load". Fixed: the checker now receives the
voice card's role, persona and demeanour, and explicitly **not** `notes`, which is the
field that holds what the author knows and the character must not.

The first version of that fix was too generous — "whatever it says about them is theirs to
assert" — and recall dropped from 6/6 to 5/6, letting through a draft that invented a
second guard's testimony. Bounded to *their own identity, and no further*, recall came back
to 6/6 over three consecutive runs. **Two iterations against the same fixture is the edge
of tuning**, and it is recorded here rather than smoothed over: the fix is principled (a
licence I wrote too broadly, narrowed to what I meant), but the next person to touch this
prompt should re-run the control before believing it, not after.

### 4. The control caught the gate out on the leak that would actually matter

The planted cases are this campaign's own secrets. Two of them leak **player-character
canon** — Corin's grifter past and Hammond's cult years, both written by Kelly and Sam at
co-creation, neither knowable by anyone at that crossroads.

Hammond's, stated flatly (*"Six years with those doomsday people, wasn't it?"*), was
caught. Corin's was not:

> *"You've got the look of a man who's run a con before. I've seen your kind work a crowd."*

It passed because it wears an impression's clothes, and impressions are explicitly
protected — a character is allowed to find you shifty. But **that is the shape a leak
actually takes at a table.** Nobody recites a secret; they let slip that they know it. A
new rule now separates reading someone's *present* off them (fair: tired, frightened,
lying) from reading their *past* off them (a claim about their life, and if it is not on
the list they do not have it).

Final control, three consecutive runs: **6/6 planted caught, 0/7 false positives.** The
clean case that guards against over-correction — the guard's own opinion, *"Far as I'm
concerned this one took it"* — passed every time.

### 5. The GM directs well, and stops itself

Seven of ten turns ended with a `[[SPEAK:]]`. The three that did not are the interesting
ones: twice the GM chose to answer with body language instead (*"His eyes go distant for a
second — counting hours, maybe, or trying not to"*), and once the party addressed the
**crowd**, who are not in the cast, so the GM voiced a bystander in its own prose exactly
as it always has. Nothing was dropped, nothing hit the two-per-turn cap, and no direction
named somebody who does not exist.

The directions themselves stayed directions rather than scripts — *"asked what he makes of
the lack of forced entry"*, *"asked whether the crate was ever on his manifest"* — which is
the property `npc_turn.direction` exists to make auditable.

### 6. The open question from (f), measured: 6 of 7

Across the seven directed turns, the GM wrote dialogue for the character it had just handed
the floor to **once** — turn 10, the caravan master's *entrance*:

> "Somebody want to tell me," he says to no one in particular, "why my crossroads looks
> like a hanging that hasn't happened yet?"

…and then the master spoke for himself. The failure has a **shape**, which is more useful
than the rate: it happens on a character's **first appearance**, where the GM is bringing
someone on stage and an entrance line is the natural way to do it. Running total since the
tier landed: **13 directed turns, 4 with GM-written dialogue; 9 since the prompt was
strengthened, 1 of those.** Still not fixed, still not tuned further — but "first
appearance" is a testable hypothesis where "sometimes" was not.

### 7. The table cost is higher than (f) measured

| | (f), a scratch NPC | here, real records |
|---|---|---|
| GM call | 4–9 s | **4.1–9.2 s** (median 5.7) |
| NPC call | 1.3–3.2 s | **5.0–9.8 s** (median 5.8) |
| whole turn, no NPC | — | **4.3–7.0 s** |
| **whole turn with a directed line** | 6.6–9.2 s | **12.1–19.7 s** |

(f)'s numbers came from a two-line voice card and a five-entry ledger. A real character
with a full card and eight facts in scope roughly doubles the NPC call, and the gate scales
with draft length on top of that. **A turn where somebody speaks costs about 15 seconds**,
and roughly a third of that is the gate.

Worth knowing before the real session: this is a pause with a shape to it — the GM's
narration streams first, then the character answers. It is not fifteen seconds of blank
screen. Whether it reads as tension or as a hang is the thing only Kelly and Sam can say.

### 8. The GM writes every player character's dialogue, and now that is conspicuous

Ten turns out of ten, the GM rendered the declared action as quoted PC speech:

> Corin's shoulders drop half an inch… *"The canvas flap on the third wagon was already
> loose when I got to it," she says.*

This is not new and P4.5 did not cause it — it is how the GM has narrated social actions
since Phase 1, and it is arguably just good prose expansion of "I tell him straight that
the flap was already loose". But the tier has made it **asymmetric**: every NPC in the
cast now speaks in their own voice, and the player characters are the only people at the
table being ventriloquised. Tagged for design below.

---

## What still has not been tested

- **Two humans.** All of the above. Also `/switch`, the hot seat, and whether anybody
  enjoys the pause.
- **A `blocked` verdict in play.** Nothing was blocked across seven live lines and 24
  control cases — every interception was a `revise`. The open question about what a block
  should cost is still unexercised as well as unruled.
- **A second scene with the same characters**, which is what P4.6 (stance-scoped
  supersession) is actually for: nothing here changed what anyone believes mid-scene.
- **The `player_known` scope**, which fills automatically at the end-of-session sweep. This
  scene's sweep was not run.

## FOR DESIGN

Two, neither blocking.

1. **Should the GM voice player characters at all, now that NPCs voice themselves?**
   Finding 8. The options are roughly: leave it (the prose is good and the players said the
   words in substance); narrow it (the GM may describe a PC speaking but not quote them);
   or the symmetric answer, which is that a PC's *own words* belong to their player and the
   GM should stop at "she tells him plainly". This is a feel question about a table Fable
   has never sat at, so Kelly's view probably matters more than mine.

2. **Carried from (d), still open:** should a `blocked` line cost the turn, or fall through
   to the GM narrating around the silence? Now with the extra datum that in a real scene
   **nothing was blocked at all** — the gate revises, it does not silence — so this may be
   a rarer case than it looked.
