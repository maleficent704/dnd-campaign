# Playtest — first play session (Corin Vale, Ashmill), 2026-08-05

**Session type:** solo (Kelly), first real `dndc play` session. 1h21m, 29 player turns,
32 GM calls, 3 checks, **$0.4961** at Sonnet API rates. Log:
`logs/20260805-063755.jsonl`. Sam did not play; no `/switch`, so hot-seat rotation is
still untested.

The session worked. Corin walked into the town of Ashmill, drank at the Grey Hollow,
eavesdropped on two locals, questioned the innkeeper about a boarded-up chapel, lifted a
coil of rope off a junk merchant, walked out to Vennhollow, and searched an abandoned
chapel where he found a camp, a silver ring, and a bloodstained altar. It read like a
session of D&D.

## What worked

- **Prose and pacing held for 29 turns.** Concrete sensory detail, NPCs with their own
  business, no drift into purple or generic. The innkeeper's wariness cooling by degrees
  as Corin bought a drink was character work, not description.
- **The backstory paid off in the first paragraph.** Turn one referenced the job that went
  sideways, the crew that ran in four directions, three months without seeing any of them
  — the two `character`-scope canon entries co-creation wrote, used as hooks immediately.
  This is D-005's stated purpose working end to end on the first attempt.
- **All content original.** Ashmill, Vennhollow, Saint Brannoc's chapel, Reeve Petrus
  Ellard, Dunnett Loam, Fenwick, Hollis. No module material, nothing outside the SRD.
- **OD-11 held completely.** Zero engine numbers in prose across 32 replies. The failed
  Perception check (5 vs DC 12) was narrated as *"Whatever put it here has kept its
  secret"* — severity fidelity without a value crossing the boundary.
- **The three checks were well chosen**: eavesdropping (Stealth), lifting the rope while
  distracting the merchant (Sleight of Hand), searching the fence post (Perception). Each
  was a genuinely uncertain action with a real cost to failing. The GM did *not* ask for
  rolls on the many conversations, which is correct.
- **Unusual player input handled gracefully.** Kelly used `*asterisk actions*`, asked
  questions rather than declaring actions (*"Can I peer into the gap first?"*), and
  improvised a solution the GM had not offered (throwing a rock in to flush anything
  nesting). All landed.

## Findings

### 1. The world is not remembered — and this is now demonstrable

29 turns authored a town, two villages, a reeve, a broken man, a sealed chapel, a
bloodstained altar and a silver ring that does not belong to whoever slept there. **None
of it is in the canon ledger.** Play never writes canon; only co-creation does. The
ledger still holds exactly the two entries about Corin's past.

Re-running `dndc play` on the same campaign immediately afterwards, the GM opened in a
city called **Kellmoor** — new city, new weather, new stranger in a good coat. Ashmill
does not exist any more.

This is Phase 2's entire justification, and it is no longer an abstract argument: there is
a log of a good session that the campaign cannot inherit. Worth preserving as the
before-picture for canon-drift work.

### 2. Scaffolding has become a formula — 23 of 32 replies end identically

Every one of those 23 closes with the literal sentence *"— or anything else you'd like to
try."* 26 of 32 contain "anything else". D-006 says the scaffolding fades as players find
their feet; nothing implements fading, and the `high` template's phrasing does not vary,
so the same sentence arrives every turn for eighty minutes.

Kelly frequently ignored the offered options and did her own thing (the rock; peering
before entering; checking the ash to date the camp), which is the signal D-006 describes
as readiness to fade. Two separable problems: the *mechanism* (nothing steps `high` →
`low` → `off`), and the *phrasing* (even at `high`, the closing should vary).

### 3. Every DC was 12

Three checks, three DCs, all 12. n=3 is weak evidence, but the design intent behind
logging `gm_adjudication` is that Phase 7 can audit whether rulings are fair — and a GM
that anchors on one number would make that analysis vacuous. The three situations had
visibly different difficulty (eavesdropping across a noisy room, palming rope from a
distracted seller, reading a months-old knot) and all priced the same.

Worth watching over the next session rather than acting on now. If it holds, the fix is
probably a DC ladder in the prompt with worked examples.

### 4. The GM did not open the scene

Kelly had to prompt the campaign into existence, and asked whether it should be doing that
itself. It should. **Fixed** — `TurnEngine.open_scene()` now runs a GM turn before the
first prompt when a campaign has no history, with its own `opening.md` template that asks
for a world already in motion. Verified live.

### 5. Picked-up items never reach the sheet

Corin stole a coil of rope, pocketed a silver ring and a whittling knife. His inventory is
unchanged. Nothing wires narrative acquisition to sheet state, so the fiction and the
character sheet have already diverged in session one. Not urgent for exploration, but it
is the same class of desynchronisation D-001 exists to prevent, and combat (Phase 3) will
make it acute.

### 6. Cost model confirmed

$0.0155/turn, $0.4961 for 81 minutes. A three-hour session extrapolates to **~$1.10**,
inside OD-10's measured $0.50–2 band. No adjustment needed.

## Not tested

Two-player hot-seat and `/switch` (Sam has no character yet), `/recap`, combat, NPC voices,
any session longer than the context window comfortably holds.

**FOR DESIGN:** nothing blocking. Finding 2 is the one that wants a ruling eventually —
D-006 specifies fading scaffolding but not what triggers a step down. Player-initiated
(`/scaffolding low`), turn-count, or a GM judgment call are all plausible; my instinct is
player-initiated plus a nudge from the GM after N turns of the player ignoring the offered
options, since that is the actual signal. Not urgent — one command would do for now.
