"""Ability checks, saving throws, and attack resolution.

Every function is pure: state and an RNG go in, a frozen result comes out. The GM
narrates these outcomes; it never produces them (D-001). Where the GM sets a DC,
that DC arrives here as a plain integer and is carried on the result so the
`gm_adjudication` event can be checked against the `rules_resolution` event later
(D-008, ruling-fairness analysis).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from dndc.rules.dice import Advantage, D20Result, DiceError, roll, roll_d20

# 5e ability score -> modifier is floor((score - 10) / 2), including negatives.
MIN_ABILITY_SCORE = 1
MAX_ABILITY_SCORE = 30


class Proficiency(str, Enum):
    """How proficient a creature is with a given check."""

    NONE = "none"
    HALF = "half"          # Jack of All Trades, some racial features
    PROFICIENT = "proficient"
    EXPERTISE = "expertise"


def ability_modifier(score: int) -> int:
    """Convert an ability score to its modifier. Rounds toward negative infinity."""
    if not MIN_ABILITY_SCORE <= score <= MAX_ABILITY_SCORE:
        raise ValueError(f"ability score {score} outside 1..30")
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """5e proficiency bonus by character level: +2 at 1-4, rising every 4 levels."""
    if not 1 <= level <= 20:
        raise ValueError(f"character level {level} outside 1..20")
    return 2 + (level - 1) // 4


def proficiency_contribution(bonus: int, proficiency: Proficiency) -> int:
    """How much of the proficiency bonus applies. Half-proficiency rounds down."""
    if proficiency is Proficiency.NONE:
        return 0
    if proficiency is Proficiency.HALF:
        return bonus // 2
    if proficiency is Proficiency.PROFICIENT:
        return bonus
    return bonus * 2  # expertise


@dataclass(frozen=True)
class CheckResult:
    """An ability check or saving throw resolved against a DC."""

    roll: D20Result
    dc: int
    success: bool
    kind: str          # "check" | "save"
    ability: str       # "dex", "wis", ...
    skill: str | None = None

    @property
    def margin(self) -> int:
        """How far the total cleared (or missed) the DC. Negative means failure."""
        return self.roll.total - self.dc


def resolve_check(
    rng: random.Random,
    *,
    ability_score: int,
    dc: int,
    level: int = 1,
    proficiency: Proficiency = Proficiency.NONE,
    advantage: Advantage = Advantage.NORMAL,
    extra_modifier: int = 0,
    ability: str = "",
    skill: str | None = None,
) -> CheckResult:
    """Resolve an ability check against a DC.

    A natural 20 or 1 on an ability check is *not* an automatic success or
    failure in 5e — that rule applies only to attack rolls (and, in this engine,
    death saves). The total is compared to the DC, full stop.
    """
    modifier = (
        ability_modifier(ability_score)
        + proficiency_contribution(proficiency_bonus(level), proficiency)
        + extra_modifier
    )
    d20 = roll_d20(rng, modifier=modifier, advantage=advantage)
    return CheckResult(
        roll=d20,
        dc=dc,
        success=d20.total >= dc,
        kind="check",
        ability=ability,
        skill=skill,
    )


def resolve_save(
    rng: random.Random,
    *,
    ability_score: int,
    dc: int,
    level: int = 1,
    proficient: bool = False,
    advantage: Advantage = Advantage.NORMAL,
    extra_modifier: int = 0,
    ability: str = "",
) -> CheckResult:
    """Resolve a saving throw against a DC. Saves are proficient or not — no expertise."""
    modifier = (
        ability_modifier(ability_score)
        + (proficiency_bonus(level) if proficient else 0)
        + extra_modifier
    )
    d20 = roll_d20(rng, modifier=modifier, advantage=advantage)
    return CheckResult(
        roll=d20,
        dc=dc,
        success=d20.total >= dc,
        kind="save",
        ability=ability,
    )


@dataclass(frozen=True)
class AttackResult:
    """An attack roll, plus damage if it landed."""

    roll: D20Result
    target_ac: int
    hit: bool
    critical: bool
    damage: int = 0
    damage_expression: str | None = None
    damage_rolls: tuple[int, ...] = ()

    @property
    def missed_by(self) -> int:
        """How far short the attack fell. Zero on a hit."""
        return max(0, self.target_ac - self.roll.total)


def resolve_attack(
    rng: random.Random,
    *,
    attack_modifier: int,
    target_ac: int,
    damage_expression: str | None = None,
    damage_modifier: int = 0,
    advantage: Advantage = Advantage.NORMAL,
) -> AttackResult:
    """Resolve an attack roll and, on a hit, its damage.

    5e attack rules applied here:
      - a natural 20 always hits and is a critical;
      - a natural 1 always misses, regardless of modifiers;
      - a critical rolls the damage dice twice, but the flat modifier once;
      - damage is floored at 0 (a large negative modifier cannot heal the target).
    """
    d20 = roll_d20(rng, modifier=attack_modifier, advantage=advantage)

    critical = d20.is_natural_20
    if d20.is_natural_1:
        hit = False
    elif critical:
        hit = True
    else:
        hit = d20.total >= target_ac

    if not hit or damage_expression is None:
        return AttackResult(
            roll=d20,
            target_ac=target_ac,
            hit=hit,
            critical=critical,
            damage_expression=damage_expression,
        )

    first = roll(damage_expression, rng)
    rolls = first.all_rolls
    dice_total = first.total - first.constant
    if critical:
        second = roll(damage_expression, rng)
        rolls += second.all_rolls
        dice_total += second.total - second.constant

    damage = max(0, dice_total + first.constant + damage_modifier)

    return AttackResult(
        roll=d20,
        target_ac=target_ac,
        hit=True,
        critical=critical,
        damage=damage,
        damage_expression=damage_expression,
        damage_rolls=rolls,
    )


__all__ = [
    "Advantage",
    "AttackResult",
    "CheckResult",
    "DiceError",
    "Proficiency",
    "ability_modifier",
    "proficiency_bonus",
    "proficiency_contribution",
    "resolve_attack",
    "resolve_check",
    "resolve_save",
]
