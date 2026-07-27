"""P0.4: standard array and point-buy allocators."""

from __future__ import annotations

import pytest

from dndc.rules.allocate import (
    POINT_BUY_BUDGET,
    STANDARD_ARRAY,
    AllocationError,
    apply_bonuses,
    assign_point_buy,
    assign_standard_array,
    point_buy_breakdown,
    point_buy_cost,
    point_buy_total,
)
from dndc.schema.sheet import Ability

A = Ability


def spread(s, d, c, i, w, ch) -> dict[Ability, int]:
    return {A.STR: s, A.DEX: d, A.CON: c, A.INT: i, A.WIS: w, A.CHA: ch}


# --- standard array --------------------------------------------------------


def test_standard_array_accepts_a_permutation():
    scores = assign_standard_array(spread(8, 15, 14, 12, 13, 10))
    assert scores.dex == 15
    assert scores.str_ == 8


def test_standard_array_rejects_a_repeated_value():
    with pytest.raises(AllocationError, match="standard array"):
        assign_standard_array(spread(15, 15, 14, 13, 12, 10))


def test_standard_array_rejects_off_array_values():
    with pytest.raises(AllocationError, match="standard array"):
        assign_standard_array(spread(16, 14, 13, 12, 10, 8))


def test_standard_array_rejects_a_missing_ability():
    partial = spread(15, 14, 13, 12, 10, 8)
    del partial[A.CHA]
    with pytest.raises(AllocationError, match="no score assigned"):
        assign_standard_array(partial)


def test_standard_array_constant_is_the_srd_spread():
    assert STANDARD_ARRAY == (15, 14, 13, 12, 10, 8)


# --- point buy -------------------------------------------------------------


@pytest.mark.parametrize(
    "score,cost", [(8, 0), (9, 1), (10, 2), (11, 3), (12, 4), (13, 5), (14, 7), (15, 9)]
)
def test_point_buy_cost_table(score, cost):
    assert point_buy_cost(score) == cost


@pytest.mark.parametrize("score", [7, 16, 18, 0])
def test_point_buy_rejects_unbuyable_scores(score):
    with pytest.raises(AllocationError, match="cannot be bought"):
        point_buy_cost(score)


def test_a_classic_27_point_spread_is_legal():
    # 15/15/15/8/8/8 = 9+9+9+0+0+0 = 27
    assignment = spread(15, 15, 15, 8, 8, 8)
    assert point_buy_total(assignment) == POINT_BUY_BUDGET
    assert assign_point_buy(assignment).con == 15


def test_underspending_the_budget_is_allowed():
    assignment = spread(8, 8, 8, 8, 8, 8)
    scores = assign_point_buy(assignment)
    assert scores.str_ == 8
    assert point_buy_total(assignment) == 0


def test_overspending_the_budget_is_rejected():
    # 15/15/15/15/8/8 = 36 points
    with pytest.raises(AllocationError, match="over the 27-point budget"):
        assign_point_buy(spread(15, 15, 15, 15, 8, 8))


def test_custom_budget_is_honoured():
    assignment = spread(15, 15, 15, 15, 8, 8)
    assert assign_point_buy(assignment, budget=40).dex == 15


def test_breakdown_reports_per_ability_cost_and_remainder():
    breakdown = point_buy_breakdown(spread(15, 14, 13, 12, 10, 8))
    assert breakdown.costs[A.STR] == 9
    assert breakdown.costs[A.CHA] == 0
    assert breakdown.spent == 9 + 7 + 5 + 4 + 2 + 0  # 27
    assert breakdown.remaining == 0


def test_breakdown_remaining_can_be_positive():
    assert point_buy_breakdown(spread(8, 8, 8, 8, 8, 8)).remaining == POINT_BUY_BUDGET


# --- bonuses ---------------------------------------------------------------


def test_species_bonuses_apply_after_allocation():
    """A 15 + 2 = 17 is legal even though 17 cannot be bought directly."""
    base = assign_point_buy(spread(8, 15, 14, 12, 13, 10))
    boosted = apply_bonuses(base, {A.DEX: 2, A.CHA: 1})
    assert boosted.dex == 17
    assert boosted.cha == 11
    assert boosted.con == 14  # untouched


def test_apply_bonuses_does_not_mutate_the_input():
    base = assign_standard_array(spread(8, 15, 14, 12, 13, 10))
    apply_bonuses(base, {A.DEX: 2})
    assert base.dex == 15


def test_bonuses_that_break_the_range_are_rejected():
    base = assign_standard_array(spread(8, 15, 14, 12, 13, 10))
    with pytest.raises(AllocationError, match="out-of-range"):
        apply_bonuses(base, {A.DEX: 20})


def test_negative_bonuses_are_allowed():
    base = assign_standard_array(spread(8, 15, 14, 12, 13, 10))
    assert apply_bonuses(base, {A.STR: -2}).str_ == 6
