"""Ability score allocators: standard array and point buy.

Pure functions with no RNG and no model calls. The GM proposes an allocation
during co-creation (D-005); these functions are what actually validate and build
it, so the engine — not the model — owns whether a spread is legal.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndc.schema.sheet import Ability, AbilityScores

#: SRD 5e standard array.
STANDARD_ARRAY: tuple[int, ...] = (15, 14, 13, 12, 10, 8)

#: SRD 5e point-buy cost table. Scores outside 8..15 cannot be bought.
POINT_BUY_COSTS: dict[int, int] = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27
POINT_BUY_MIN = 8
POINT_BUY_MAX = 15


class AllocationError(ValueError):
    """Raised when a proposed ability spread is not legal for its method."""


def _to_scores(assignment: dict[Ability, int]) -> AbilityScores:
    missing = [a.value for a in Ability if a not in assignment]
    if missing:
        raise AllocationError(f"no score assigned for: {', '.join(missing)}")
    extra = [k for k in assignment if not isinstance(k, Ability)]
    if extra:
        raise AllocationError(f"unknown ability keys: {extra}")
    return AbilityScores.model_validate(
        {
            "str": assignment[Ability.STR],
            "dex": assignment[Ability.DEX],
            "con": assignment[Ability.CON],
            "int": assignment[Ability.INT],
            "wis": assignment[Ability.WIS],
            "cha": assignment[Ability.CHA],
        }
    )


def assign_standard_array(assignment: dict[Ability, int]) -> AbilityScores:
    """Build scores from the standard array.

    The assignment must be a permutation of STANDARD_ARRAY — each of the six
    values used exactly once.
    """
    scores = _to_scores(assignment)
    used = sorted(assignment.values(), reverse=True)
    if tuple(used) != STANDARD_ARRAY:
        raise AllocationError(
            f"standard array must use {list(STANDARD_ARRAY)} exactly once each, got {used}"
        )
    return scores


def point_buy_cost(score: int) -> int:
    """Point cost of a single score. Raises for anything outside the buyable range."""
    if score not in POINT_BUY_COSTS:
        raise AllocationError(
            f"score {score} cannot be bought; point buy allows {POINT_BUY_MIN}..{POINT_BUY_MAX}"
        )
    return POINT_BUY_COSTS[score]


def point_buy_total(assignment: dict[Ability, int]) -> int:
    """Total points a spread costs. Raises if any score is unbuyable."""
    return sum(point_buy_cost(v) for v in assignment.values())


def assign_point_buy(
    assignment: dict[Ability, int], budget: int = POINT_BUY_BUDGET
) -> AbilityScores:
    """Build scores from a point-buy spread, enforcing the budget.

    Spending less than the full budget is legal (players may leave points on the
    table); spending more is not.
    """
    scores = _to_scores(assignment)
    spent = point_buy_total(assignment)
    if spent > budget:
        raise AllocationError(f"point buy costs {spent}, over the {budget}-point budget")
    return scores


@dataclass(frozen=True)
class PointBuyBreakdown:
    """Per-ability costs and the remaining budget — for showing a player their spend."""

    costs: dict[Ability, int]
    spent: int
    budget: int

    @property
    def remaining(self) -> int:
        return self.budget - self.spent


def point_buy_breakdown(
    assignment: dict[Ability, int], budget: int = POINT_BUY_BUDGET
) -> PointBuyBreakdown:
    costs = {ability: point_buy_cost(score) for ability, score in assignment.items()}
    return PointBuyBreakdown(costs=costs, spent=sum(costs.values()), budget=budget)


def apply_bonuses(scores: AbilityScores, bonuses: dict[Ability, int]) -> AbilityScores:
    """Apply species or feat bonuses on top of a base spread.

    Returns a new AbilityScores — the input is never mutated. Bonuses apply
    *after* allocation, which is why a 15 + 2 = 17 is legal under point buy even
    though 17 cannot be bought directly.
    """
    combined = scores.as_dict()
    for ability, bonus in bonuses.items():
        combined[ability] = combined[ability] + bonus
    try:
        return _to_scores(combined)
    except Exception as exc:  # pydantic range violation
        raise AllocationError(f"bonuses produced an out-of-range score: {exc}") from exc
