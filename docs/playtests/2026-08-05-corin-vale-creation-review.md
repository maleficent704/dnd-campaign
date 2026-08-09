# Playtest finding — character creation review (Corin Vale), 2026-08-05

**Session type:** solo (Kelly), first live co-creation interview by a player rather than
by CC. Reviewed by Fable against SRD 5.1. The interview UX, pacing, and canon extraction
were good; the sheet has systematic omissions.

## The character (context)

Half-Elf Charlatan Rogue 1 "Corin Vale", face-skill build (Cha 16 / Dex 15). Canon
entries (2) are well-chosen, correctly scoped `character`, and genuinely hook-rich —
scattered crew with unknown fates is payoff material. Fixed grants on the sheet are all
correct: rogue saves (dex/int), 4 class skills from the rogue list, HP 9 (8+con), AC 13
(leather+dex), speed 30, weapon/armor proficiencies.

## Bugs (all in `rules/build.py` / creation flow, none in the GM's judgment)

1. **Half-Elf floating +1s never applied.** +2 Cha landed; the "+1 to two other
   abilities of your choice" did not — no base-array arrangement reproduces the final
   scores with the bonuses included. The sheet is 2 ability points short.
2. **Thieves' tools proficiency missing.** Fixed rogue class grant (not a choice). The
   item is in inventory; `proficiencies.tools` is empty.
3. **Rogue Expertise missing.** Level-1 class feature: two proficiencies (skills or
   thieves' tools) at expertise. Schema supports `expertise`; all four skills emitted as
   `proficient`.
4. **Half-Elf bonus language missing.** Species grants one extra language of choice;
   only Common + Elvish emitted.

## The pattern (this is the finding)

**Confirmed from the control side, same day:** a standard human fighter (Brother
Hammond, flat +1-to-all species bonuses — zero choice-points) came out of the same
flow with every ability, save, skill, AC, and HP value correct. The only omissions
were, again, choices: Fighting Style and the human bonus language. Choice-dependent
grants are the bug's exact boundary.

Every omission except the tools proficiency is a **choice-point inside a species/class
grant**. Fixed grants all came through; grants requiring a player/GM choice were
silently dropped — `Concept`/the `[[PROPOSE]]` format presumably has no slot for them,
and `build.py` doesn't fail loudly when a required choice is absent. Suggested shape of
the fix, for CC to take or improve on:

- `Concept` grows explicit fields for required choices (floating ability bonuses,
  expertise picks, bonus languages); the creation prompt instructs the GM to settle them
  in the interview (they are concept questions — "what did she pick up in her grifter
  years" — not bookkeeping).
- `build.py` **raises** when a species/class demands a choice the concept doesn't
  carry — a silently short sheet is exactly the drift the deterministic tier exists to
  prevent. The repair path already exists for routing that back to the GM.
- A validator pass comparing emitted sheets against SRD grants for the species/class
  would have caught 1–4 mechanically; worth adding as a test fixture over a few
  species/class combos.
- Related, already-queued: backgrounds (Charlatan would grant deception + sleight of
  hand). When that data task lands, the class-skill picker must avoid double-granting
  what the background provides.

## Interim state

Kelly will hand-edit Corin's YAML per D-005 (sheets are re-editable data) once she picks
her +1s / expertise / language, and re-validate. Sam's interview should ideally wait for
the fix, or accept the same hand-edit pass.

**FOR DESIGN:** none — this is implementation against already-ratified rules. Fable has
reviewed; proceed with the fix as a P1.5-adjacent bug task (live-run rule applies:
re-run a creation interview end to end and diff the sheet against SRD grants).
