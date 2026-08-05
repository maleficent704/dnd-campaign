"""Qualitative severity for engine outcomes (OD-11).

D-001 as amended bans engine-resolved numbers from the GM's prose and puts a corollary
obligation in their place: **severity fidelity**. With the numbers gone, description is
the players' only handle on how much trouble they are in, so it has to track magnitude.

That obligation needs a signal to track. These functions turn a resolved outcome into a
severity band the GM can narrate, computed deterministically from the same numbers the
interface displays. The GM is told "failed badly", not "rolled 7 against DC 15" — it
cannot restate a number it was never given, which makes the ban structural rather than a
matter of the model remembering an instruction.

Pure functions over ints. No model, no state.
"""

from __future__ import annotations

from dndc.rules.checks import CheckResult

#: Margin bands for a check, in points clear of (or short of) the DC. 5e DCs move in
#: fives, so a 10-point margin is two full difficulty steps — comfortably decisive.
DECISIVE_MARGIN = 10
NARROW_MARGIN = 5


def check_severity(result: CheckResult) -> str:
    """How emphatically a check succeeded or failed."""
    margin = result.margin
    if result.success:
        if margin >= DECISIVE_MARGIN:
            return "succeeded decisively"
        if margin < NARROW_MARGIN:
            return "succeeded, but only barely"
        return "succeeded"
    shortfall = -margin
    if shortfall >= DECISIVE_MARGIN:
        return "failed badly"
    if shortfall < NARROW_MARGIN:
        return "failed, but only just"
    return "failed"


def damage_severity(damage: int, current_hp: int, maximum_hp: int) -> str:
    """How hard a hit landed, relative to what the character can take.

    Relative rather than absolute: 6 damage is a scratch to a barbarian and near-lethal
    to a level 1 wizard, and the players' felt sense should track the second reading.
    `current_hp` is the value *after* the damage was applied.
    """
    if maximum_hp <= 0:
        return "wounded"
    if current_hp <= 0:
        return "dropped — unconscious and dying"
    if damage <= 0:
        return "unharmed"

    fraction = damage / maximum_hp
    remaining = current_hp / maximum_hp

    if remaining <= 0.25:
        return "gravely wounded and barely standing"
    if fraction >= 0.5:
        return "hit devastatingly hard"
    if fraction >= 0.25:
        return "seriously wounded"
    if fraction <= 0.1:
        return "barely scratched"
    return "wounded"


def describe_check(result: CheckResult, actor: str) -> str:
    """The line handed to the GM. Deliberately carries no numbers (OD-11)."""
    what = result.skill or result.ability or "ability"
    label = what.replace("_", " ")
    return f"{actor}'s {label} {result.kind} {check_severity(result)}."
