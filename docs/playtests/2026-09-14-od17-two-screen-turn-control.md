# Playtest instrument — OD-17: what a two-screen table does with the turn

**Status: the sheet is blank and that is correct.** This file is the *instrument*, not a
result. It is filled in during one real evening and then it decides something.

**Raised:** 2026-09-13 · **Ruled:** 2026-09-14 (Fable, claude-ai) · **Instrument written:**
2026-09-14 (b)

---

## What this decides

Fable ruled OD-17 in three parts, and the third part is this file:

1. **Auto-rotate is rejected permanently.** Turn order taken from the party roster is wrong
   the moment one character should act twice. Ordered turns are combat's job (initiative),
   not conversation's. Nothing here can reopen that.
2. **Claim, if it is ever built, is a soft per-device default and never an identity** — a
   cookie or `localStorage` preference that pre-selects which character this device's turns
   act as, overridable on any turn, invisible to the server's trust model. No per-device
   identity, no locks, no conflict semantics; two devices defaulting to the same character
   is legal and merely redundant. The token gate's *everyone holding the key is the same
   person* design is deliberate and stays.
3. **Whether part 2 is worth building is decided by this evening.** Near-zero friction:
   keep explicit `/switch` and close OD-17 with no build. Real friction: build exactly part
   2 and nothing more.

> *"The playtest note is the instrument; nothing is built speculatively."*

The honest version of that instruction is that **this file is allowed to say "keep what we
have".** A sheet that can only ever justify building something is not an instrument.

## How to run it

An ordinary evening. Two devices, one campaign, the `/switch` that exists today. **Do not
change how you play in order to measure it** — an evening played carefully to avoid
mistakes measures the care, not the interface.

One person keeps this file open, or a scrap of paper, and makes a mark in one of two
columns whenever either thing happens. That is the whole protocol.

## The two counts

**A — wrong-character actions.** A turn was taken, or begun, as the wrong character.
Includes: typing an action and realising afterwards it went in as the other PC; starting to
type and stopping because the header said the wrong name; a turn that had to be narrated
around because it came from the wrong person.

**B — stop-and-switch moments.** Play paused while somebody said a version of *"switch to
me first"*. The turn itself was fine; the evening stopped to arrange it.

They are separate because they cost different things. **A is a wrong turn in the log and in
the campaign.** B is friction only — and B is the one soft-claim would actually remove,
since a device that already knows who it usually is does not need to be told each time.

|   | Count | Notes — what happened, in a few words |
|---|-------|---------------------------------------|
| **A** — wrong-character actions | | |
| **B** — stop-and-switch moments | | |

**Turns played this evening:** ___  ·  **Devices in use:** ___  ·  **Same room / different rooms:** ___

## Reading it afterwards

Rates, not totals — a twelve-turn evening and a forty-turn evening are not comparable.

- **A + B at or near zero across a full evening → keep `/switch`, close OD-17, build
  nothing.** Two people who hand the keyboard over out loud are not a problem an interface
  needs to solve, and this is the outcome that costs nothing and is allowed to win.
- **B recurring, A near zero → build soft-claim** exactly as part 2 scopes it. The friction
  is the announcing, which is exactly what a per-device default removes.
- **A recurring → say so here and stop.** Wrong turns are a different failure from friction,
  and a default that pre-selects a character can make them *worse* rather than better — a
  device that quietly assumes who you are is a device that can be quietly wrong. That
  outcome is not what part 2 was scoped against, and it wants its own ruling rather than
  the build this file was written to authorise.

Anything else — a pattern neither column anticipated, one room behaving unlike the other —
is worth more than the numbers. Write it in the notes column and say so in the handoff
entry; the counts exist to make a vague feeling checkable, not to overrule one.

## Result

*(Fill in after the evening. Then record the outcome in `docs/PROGRESS.md` and close or
advance OD-17 in `docs/DESIGN-DECISIONS.md`.)*

**Date played:**
**Who was at the table:**
**Outcome:**
