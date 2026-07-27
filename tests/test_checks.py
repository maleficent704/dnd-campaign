"""P0.3: ability checks, saving throws, and attack resolution."""

from __future__ import annotations

import random

import pytest

from dndc.rules.checks import (
    Advantage,
    Proficiency,
    ability_modifier,
    proficiency_bonus,
    proficiency_contribution,
    resolve_attack,
    resolve_check,
    resolve_save,
)


def rng(seed: int = 2024) -> random.Random:
    return random.Random(seed)


class FixedRandom(random.Random):
    """A Random that yields a scripted sequence of d20 faces, then falls back to seeded."""

    def __init__(self, faces, seed=0):
        super().__init__(seed)
        self._faces = list(faces)

    def randint(self, a, b):
        if self._faces and (a, b) == (1, 20):
            return self._faces.pop(0)
        return super().randint(a, b)


# --- modifiers -------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [(1, -5), (3, -4), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (15, 2), (20, 5), (30, 10)],
)
def test_ability_modifier(score, expected):
    assert ability_modifier(score) == expected


@pytest.mark.parametrize("score", [0, -1, 31])
def test_ability_modifier_rejects_out_of_range(score):
    with pytest.raises(ValueError):
        ability_modifier(score)


@pytest.mark.parametrize(
    "level,expected",
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus(level, expected):
    assert proficiency_bonus(level) == expected


@pytest.mark.parametrize("level", [0, 21])
def test_proficiency_bonus_rejects_out_of_range(level):
    with pytest.raises(ValueError):
        proficiency_bonus(level)


def test_proficiency_contribution():
    assert proficiency_contribution(3, Proficiency.NONE) == 0
    assert proficiency_contribution(3, Proficiency.HALF) == 1     # rounds down
    assert proficiency_contribution(3, Proficiency.PROFICIENT) == 3
    assert proficiency_contribution(3, Proficiency.EXPERTISE) == 6


# --- checks and saves ------------------------------------------------------


def test_check_applies_ability_and_proficiency():
    r = FixedRandom([10])
    result = resolve_check(r, ability_score=16, dc=15, level=5, proficiency=Proficiency.PROFICIENT)
    # 10 natural + 3 (Dex 16) + 3 (level 5 proficiency) = 16
    assert result.roll.total == 16
    assert result.success is True
    assert result.margin == 1


def test_check_failure_reports_negative_margin():
    result = resolve_check(FixedRandom([2]), ability_score=10, dc=15)
    assert result.success is False
    assert result.margin == -13


def test_natural_20_on_a_check_is_not_an_automatic_success():
    """5e: auto-success on a nat 20 applies to attacks, not ability checks."""
    result = resolve_check(FixedRandom([20]), ability_score=10, dc=30)
    assert result.roll.is_natural_20 is True
    assert result.success is False


def test_natural_1_on_a_check_is_not_an_automatic_failure():
    result = resolve_check(FixedRandom([1]), ability_score=20, dc=5)
    assert result.roll.is_natural_1 is True
    assert result.success is True  # 1 + 5 = 6 >= 5


def test_save_uses_flat_proficiency_not_expertise():
    proficient = resolve_save(FixedRandom([10]), ability_score=14, dc=10, level=9, proficient=True)
    assert proficient.roll.total == 10 + 2 + 4  # +2 Con, +4 proficiency at level 9
    assert proficient.kind == "save"


def test_check_carries_the_dc_for_later_adjudication_audit():
    """D-008: the resolution event must record the DC the GM set."""
    result = resolve_check(rng(), ability_score=12, dc=17, ability="dex", skill="acrobatics")
    assert result.dc == 17
    assert result.ability == "dex"
    assert result.skill == "acrobatics"


def test_extra_modifier_is_additive():
    plain = resolve_check(FixedRandom([10]), ability_score=10, dc=10)
    buffed = resolve_check(FixedRandom([10]), ability_score=10, dc=10, extra_modifier=4)
    assert buffed.roll.total - plain.roll.total == 4


# --- attacks ---------------------------------------------------------------


def test_natural_20_always_hits_and_crits():
    result = resolve_attack(FixedRandom([20]), attack_modifier=-5, target_ac=30)
    assert result.hit is True
    assert result.critical is True


def test_natural_1_always_misses():
    result = resolve_attack(FixedRandom([1]), attack_modifier=+20, target_ac=5)
    assert result.hit is False
    assert result.critical is False
    assert result.damage == 0


def test_ordinary_hit_compares_total_to_ac():
    hit = resolve_attack(FixedRandom([12]), attack_modifier=3, target_ac=15)
    miss = resolve_attack(FixedRandom([11]), attack_modifier=3, target_ac=15)
    assert hit.hit is True
    assert miss.hit is False
    assert miss.missed_by == 1


def test_critical_doubles_dice_but_not_the_flat_modifier():
    r = FixedRandom([20], seed=11)
    crit = resolve_attack(
        r, attack_modifier=5, target_ac=10, damage_expression="1d8+3", damage_modifier=0
    )
    # Two damage dice rolled, one flat +3 applied.
    assert len(crit.damage_rolls) == 2
    assert crit.damage == sum(crit.damage_rolls) + 3


def test_normal_hit_rolls_damage_dice_once():
    hit = resolve_attack(
        FixedRandom([15], seed=11), attack_modifier=5, target_ac=10, damage_expression="2d6+2"
    )
    assert len(hit.damage_rolls) == 2
    assert hit.damage == sum(hit.damage_rolls) + 2


def test_miss_rolls_no_damage():
    miss = resolve_attack(
        FixedRandom([2]), attack_modifier=0, target_ac=20, damage_expression="1d12+4"
    )
    assert miss.damage == 0
    assert miss.damage_rolls == ()


def test_damage_floors_at_zero():
    result = resolve_attack(
        FixedRandom([18], seed=3),
        attack_modifier=5,
        target_ac=10,
        damage_expression="1d4",
        damage_modifier=-20,
    )
    assert result.hit is True
    assert result.damage == 0


def test_attack_with_advantage_rolls_two_dice():
    result = resolve_attack(
        rng(), attack_modifier=4, target_ac=14, advantage=Advantage.ADVANTAGE
    )
    assert len(result.roll.rolls) == 2


def test_attack_damage_is_reproducible_for_a_given_seed():
    def once():
        return resolve_attack(
            rng(77), attack_modifier=8, target_ac=12, damage_expression="2d6+4"
        )

    assert once().damage == once().damage


def test_attack_bounds_over_many_trials():
    r = rng(555)
    for _ in range(400):
        result = resolve_attack(
            r, attack_modifier=5, target_ac=15, damage_expression="1d8+3"
        )
        if result.hit:
            lo, hi = (2 + 3, 16 + 3) if result.critical else (1 + 3, 8 + 3)
            assert lo <= result.damage <= hi
        else:
            assert result.damage == 0
