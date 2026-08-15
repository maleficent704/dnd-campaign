"""P3.5 — building an encounter to a budget we had to invent and chose to measure.

The SRD has no encounter-building tables: XP thresholds by level and the group multiplier
are DMG content, outside D-007's licence. So the budget is ours, and the interesting
property is not that the arithmetic is right but that the numbers were **checked against
the combat engine** rather than asserted.

What is defended here:

* the budget is monotonic in difficulty and in party strength — the arithmetic cannot be
  quietly non-sensical even where the calibration is provisional;
* an encounter has a *shape*: the count is chosen before the monsters, because one large
  monster against four characters gets one turn to their four and a builder that ignores
  that prices encounters backwards (the simulation caught exactly this);
* the simulator reports what happened rather than what was hoped.
"""

from __future__ import annotations

import random

import pytest

from dndc.rules.encounter import (
    Difficulty,
    EncounterError,
    adjusted_xp,
    build,
    group_multiplier,
    simulate,
    xp_budget,
)
from dndc.srd.repository import SRDRepository


@pytest.fixture(scope="module")
def pool():
    return list(SRDRepository.load().data.monsters.values())


# --- the budget --------------------------------------------------------------


def test_the_budget_rises_with_difficulty():
    levels = [1, 1, 1, 1]
    budgets = [xp_budget(levels, d) for d in Difficulty]
    assert budgets == sorted(budgets)
    assert len(set(budgets)) == len(budgets)


def test_the_budget_rises_with_party_size_and_level():
    assert xp_budget([1, 1]) < xp_budget([1, 1, 1])
    assert xp_budget([1, 1, 1, 1]) < xp_budget([3, 3, 3, 3])


def test_levels_are_summed_rather_than_averaged():
    """A level-5 fighter beside two level-1s is not three level-2s, and the sum is the
    only honest reading of that."""
    assert xp_budget([5, 1, 1]) != xp_budget([2, 2, 2])


def test_a_party_of_nobody_has_no_budget():
    assert xp_budget([]) == 0


def test_a_level_beyond_the_ingest_scope_does_not_crash():
    """CR 0-5 is what is ingested, so levels 1-5 are what the bands claim. Past that the
    top value is reused, which is a guess — but a guess is better than a KeyError."""
    assert xp_budget([9]) == xp_budget([5])


# --- the group multiplier ----------------------------------------------------


def test_a_group_is_worth_more_than_its_parts():
    """Six dretch beat four level-1 characters 93% of the time while two giant eagles
    lost more often than they won. At these levels action economy dominates so completely
    that a flat XP sum prices a swarm as a pushover."""
    assert group_multiplier(6) > group_multiplier(2) > group_multiplier(1) == 1.0


def test_the_multiplier_never_shrinks_as_the_group_grows():
    values = [group_multiplier(n) for n in range(1, 15)]
    assert values == sorted(values)


def test_an_empty_group_is_not_a_division_by_zero():
    assert group_multiplier(0) == 1.0
    assert adjusted_xp([]) == 0


# --- building ----------------------------------------------------------------


def test_an_encounter_fits_its_budget(pool):
    for difficulty in Difficulty:
        plan = build(pool, [1, 1, 1, 1], difficulty, rng=random.Random(4))
        assert plan.adjusted_xp <= plan.budget
        assert plan.monsters


def test_the_same_seed_builds_the_same_encounter(pool):
    first = build(pool, [3, 3, 3], rng=random.Random(9))
    second = build(pool, [3, 3, 3], rng=random.Random(9))
    assert [m.index for m in first.monsters] == [m.index for m in second.monsters]


def test_the_count_is_chosen_before_the_monster(pool):
    """The bug the simulation caught: filling greedily from the biggest affordable monster
    down bought *easier* fights at harder budgets, because one large monster against four
    characters gets one turn to their four."""
    plan = build(pool, [1, 1, 1, 1], Difficulty.DEADLY, rng=random.Random(4))
    assert plan.count > 1


def test_a_challenge_ceiling_is_respected(pool):
    plan = build(pool, [5, 5, 5, 5], Difficulty.DEADLY, rng=random.Random(1), max_challenge=1)
    assert all(m.challenge_rating <= 1 for m in plan.monsters)


def test_a_monster_cap_is_respected(pool):
    plan = build(pool, [5, 5, 5, 5], Difficulty.DEADLY, rng=random.Random(1), max_monsters=2)
    assert plan.count <= 2


def test_an_empty_pool_is_an_error():
    with pytest.raises(EncounterError):
        build([], [1, 1])


def test_a_party_of_nobody_is_an_error(pool):
    with pytest.raises(EncounterError):
        build(pool, [])


def test_a_pool_of_nothing_affordable_is_an_error(pool):
    """A ceiling below the cheapest monster leaves nothing to pick, which is an error
    worth raising rather than an empty encounter worth returning."""
    with pytest.raises(EncounterError):
        build(pool, [1], Difficulty.EASY, rng=random.Random(1), max_challenge=-1)


def test_a_plan_reads_as_a_sentence(pool):
    plan = build(pool, [1, 1, 1, 1], Difficulty.HARD, rng=random.Random(4))
    rendered = plan.render()
    assert "hard" in rendered and "XP" in rendered


# --- the simulator -----------------------------------------------------------


def test_the_simulator_totals_what_happened():
    def always_win(rng):
        return True, 0, 0, 3

    result = simulate(always_win, fights=10)
    assert result.fights == 10 and result.win_rate == 1.0
    assert result.death_rate == 0.0 and result.median_rounds == 3


def test_the_simulator_counts_a_fight_once_however_many_dropped():
    """"Someone went down" is the question a table asks, not "how many"."""
    def bloody(rng):
        return True, 3, 1, 5

    result = simulate(bloody, fights=4)
    assert result.down_rate == 1.0 and result.death_rate == 1.0


def test_the_simulator_is_reproducible():
    def flaky(rng):
        return rng.random() > 0.5, 0, 0, 2

    assert simulate(flaky, fights=30, seed=7).party_wins == simulate(
        flaky, fights=30, seed=7
    ).party_wins


def test_an_unrun_simulation_reports_zeroes_rather_than_dividing_by_zero():
    result = simulate(lambda rng: (True, 0, 0, 1), fights=0)
    assert result.win_rate == 0.0 and result.median_rounds == 0.0


def test_the_summary_says_what_it_measured():
    result = simulate(lambda rng: (True, 1, 0, 4), fights=5)
    summary = result.summary()
    assert "fights" in summary and "wins" in summary
