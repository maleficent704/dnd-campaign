"""P0.3: dice expression parsing and rolling.

Every test drives a seeded `random.Random`, so failures are reproducible.
"""

from __future__ import annotations

import random

import pytest

from dndc.rules.dice import (
    Advantage,
    DiceError,
    net_advantage,
    parse,
    roll,
    roll_d20,
)


def rng(seed: int = 1234) -> random.Random:
    return random.Random(seed)


# --- parsing ---------------------------------------------------------------


def test_parse_simple():
    groups, constant = parse("2d6+3")
    assert constant == 3
    assert len(groups) == 1
    assert (groups[0].count, groups[0].sides, groups[0].sign) == (2, 6, 1)


def test_parse_implicit_count_is_one():
    groups, _ = parse("d20")
    assert groups[0].count == 1


def test_parse_negative_group_and_constant():
    groups, constant = parse("1d8-1d4-2")
    assert constant == -2
    assert [g.sign for g in groups] == [1, -1]


def test_parse_is_whitespace_and_case_insensitive():
    assert parse("2D6 + 3") == parse("2d6+3")


def test_parse_keep_and_drop_modifiers():
    kh, _ = parse("4d6kh3")
    dl, _ = parse("4d6dl1")
    # Dropping the lowest of 4 is the same selection as keeping the highest 3.
    assert kh[0].keep_highest == 3
    assert dl[0].keep_highest == 3


@pytest.mark.parametrize(
    "expr",
    [
        "",
        "   ",
        "d",
        "2d",
        "abc",
        "2d6 3",      # missing operator — must not fuse into "2d63"
        "2d 6",       # whitespace inside a term
        "0d6",        # zero dice
        "2d1",        # a 1-sided die is not a die
        "2d6kh3",     # keep more than rolled
        "2d6dl2",     # drop everything
        "1001d6",     # over MAX_DICE
        "1d1001",     # over MAX_SIDES
    ],
)
def test_parse_rejects_malformed(expr):
    with pytest.raises(DiceError):
        parse(expr)


# --- rolling ---------------------------------------------------------------


def test_roll_is_reproducible_for_a_given_seed():
    assert roll("4d6kh3+2", rng()).total == roll("4d6kh3+2", rng()).total


def test_roll_totals_match_kept_dice_plus_constant():
    result = roll("3d8+5", rng())
    assert result.total == sum(result.groups[0].kept) + 5
    assert result.constant == 5


def test_roll_respects_bounds_over_many_trials():
    r = rng(99)
    for _ in range(500):
        result = roll("2d6+3", r)
        assert 5 <= result.total <= 15
        assert all(1 <= die <= 6 for die in result.all_rolls)


def test_keep_highest_selects_the_right_dice():
    r = rng(7)
    for _ in range(200):
        result = roll("4d6kh3", r)
        group = result.groups[0]
        assert len(group.rolls) == 4
        assert len(group.kept) == 3
        # The dropped die is never larger than the smallest kept die.
        dropped = sorted(group.rolls)[0]
        assert dropped <= min(group.kept)
        assert group.subtotal == sum(group.kept)


def test_keep_lowest_selects_the_right_dice():
    r = rng(8)
    for _ in range(200):
        group = roll("4d6kl1", r).groups[0]
        assert group.kept == (min(group.rolls),) or len(group.kept) == 1
        assert group.kept[0] == min(group.rolls)


def test_negative_group_subtracts():
    result = roll("1d1000-1d1000", rng(3))
    assert result.total == result.groups[0].subtotal + result.groups[1].subtotal
    assert result.groups[1].subtotal <= 0


def test_constant_only_expression():
    result = roll("7", rng())
    assert result.total == 7
    assert result.groups == ()


# --- d20 -------------------------------------------------------------------


def test_roll_d20_normal_uses_one_die():
    result = roll_d20(rng(), modifier=3)
    assert len(result.rolls) == 1
    assert result.total == result.natural + 3


def test_advantage_takes_the_higher_of_two():
    r = rng(42)
    for _ in range(200):
        result = roll_d20(r, advantage=Advantage.ADVANTAGE)
        assert len(result.rolls) == 2
        assert result.natural == max(result.rolls)


def test_disadvantage_takes_the_lower_of_two():
    r = rng(43)
    for _ in range(200):
        result = roll_d20(r, advantage=Advantage.DISADVANTAGE)
        assert result.natural == min(result.rolls)


def test_advantage_beats_normal_on_average():
    """Statistical sanity: advantage should average clearly higher than normal."""
    r = rng(2026)
    trials = 3000
    normal = sum(roll_d20(r).natural for _ in range(trials)) / trials
    adv = sum(roll_d20(r, advantage=Advantage.ADVANTAGE).natural for _ in range(trials)) / trials
    assert adv > normal + 1.5  # theory: 13.825 vs 10.5


def test_natural_20_and_1_flags():
    r = rng(5)
    seen_20 = seen_1 = False
    for _ in range(500):
        result = roll_d20(r)
        assert result.is_natural_20 == (result.natural == 20)
        assert result.is_natural_1 == (result.natural == 1)
        seen_20 |= result.is_natural_20
        seen_1 |= result.is_natural_1
    assert seen_20 and seen_1


@pytest.mark.parametrize(
    "adv,dis,expected",
    [
        (False, False, Advantage.NORMAL),
        (True, False, Advantage.ADVANTAGE),
        (False, True, Advantage.DISADVANTAGE),
        (True, True, Advantage.NORMAL),  # 5e: they cancel, they don't stack
    ],
)
def test_net_advantage(adv, dis, expected):
    assert net_advantage(adv, dis) is expected
