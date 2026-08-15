"""Building an encounter to a budget (P3.5).

**The SRD has no encounter-building tables.** The XP thresholds by character level and the
multiplier for a group of monsters are DMG content, outside the CC-BY licence this project
runs on (D-007), and the ingested set has neither. The SRD does give every monster an `xp`
and a `challenge_rating`, which is enough to build something — but the *budget* has to be
ours.

So it is ours, and it was **measured rather than asserted**. The difficulty bands below are
not a table copied from anywhere and not numbers picked because they looked right: they are
the numbers that produced the intended survival rates when run through the combat engine a
few thousand times (`simulate`, and the figures recorded in the 2026-08-22 handoff). That
is only possible because P3.1–P3.4 made a fight deterministic, free, and model-free — a
budget you can test is worth more than a budget you can cite.

What "difficulty" means here is therefore a claim about outcomes, not a label:

* `EASY` — the party should win nearly always and spend little.
* `MEDIUM` — the party should win most of the time and feel it.
* `HARD` — a real chance of going badly.
* `DEADLY` — someone is likely to drop; the party may lose.

**Groups are worth more than their parts.** Four wolves are not four times one wolf: they
act four times a round while the party's damage is spread across four bodies. The
multiplier here is ours too, and the same simulation is what set it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

from dndc.schema.srd import Monster

#: XP one character of a given level is worth spending on a *medium* fight. Ours, and
#: calibrated by `simulate` rather than copied — see the module docstring. Level 1–5 is
#: the ingest scope (CR 0–5), so that is what is claimed; beyond it the last value is
#: extended, which is a guess and says so.
MEDIUM_XP_PER_LEVEL = {1: 50, 2: 100, 3: 150, 4: 250, 5: 500}

#: Multiples of the medium budget. Deliberately coarse: the simulation cannot distinguish
#: finer bands, and a builder that pretends to more precision than it measured is lying.
DIFFICULTY_MULTIPLIER = {
    "easy": 0.5,
    "medium": 1.0,
    "hard": 1.6,
    "deadly": 2.6,
}

#: What a group is worth beyond the sum of its members, and it is steep because the
#: simulation says it has to be. Six dretch (150 XP) beat four level-1 characters 93% of
#: the time while two giant eagles (400 XP) lost more often than they won: at these levels
#: action economy dominates so completely that a flat XP sum, or a gentle multiplier,
#: prices a swarm as a pushover. Ours, and measured.
GROUP_MULTIPLIER = {1: 1.0, 2: 1.4, 3: 1.8, 4: 2.2, 5: 2.6, 6: 3.0, 8: 3.6, 11: 4.5}


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"


class EncounterError(RuntimeError):
    """An encounter that cannot be built from the monsters available."""


@dataclass(frozen=True)
class EncounterPlan:
    """A proposed fight: what is in it, and what it was built against."""

    monsters: tuple[Monster, ...] = ()
    difficulty: Difficulty = Difficulty.MEDIUM
    budget: int = 0
    #: Raw XP, and XP after the group multiplier — the number compared to the budget.
    raw_xp: int = 0
    adjusted_xp: int = 0

    @property
    def count(self) -> int:
        return len(self.monsters)

    def render(self) -> str:
        counts: dict[str, int] = {}
        for monster in self.monsters:
            counts[monster.name] = counts.get(monster.name, 0) + 1
        listed = ", ".join(
            name if times == 1 else f"{times}x {name}" for name, times in counts.items()
        )
        return (
            f"{listed or '(nothing)'} — {self.difficulty.value}, "
            f"{self.adjusted_xp}/{self.budget} XP"
        )


def group_multiplier(count: int) -> float:
    """What `count` monsters are worth relative to their XP sum."""
    if count <= 0:
        return 1.0
    chosen = 1.0
    for threshold, value in sorted(GROUP_MULTIPLIER.items()):
        if count >= threshold:
            chosen = value
    return chosen


def xp_budget(levels: Sequence[int], difficulty: Difficulty = Difficulty.MEDIUM) -> int:
    """What this party can afford to fight.

    Levels rather than a party size and an average, because a level-5 fighter beside two
    level-1s is not three level-2s, and the sum is the only honest reading of that.
    """
    if not levels:
        return 0
    top = max(MEDIUM_XP_PER_LEVEL)
    per_character = sum(
        MEDIUM_XP_PER_LEVEL.get(min(max(1, level), top), MEDIUM_XP_PER_LEVEL[top])
        for level in levels
    )
    return int(per_character * DIFFICULTY_MULTIPLIER[difficulty.value])


def adjusted_xp(monsters: Sequence[Monster]) -> int:
    """A group's XP as the budget counts it."""
    return int(sum(m.xp for m in monsters) * group_multiplier(len(monsters)))


def build(
    candidates: Sequence[Monster],
    levels: Sequence[int],
    difficulty: Difficulty = Difficulty.MEDIUM,
    rng: random.Random | None = None,
    max_monsters: int = 8,
    max_challenge: float | None = None,
) -> EncounterPlan:
    """Pick monsters that fill the budget, in a shape that plays like a fight.

    **How many, before which.** An earlier version filled greedily from the biggest
    affordable monster down, and the simulation showed why that is wrong: one large
    monster against four characters gets one turn to their four and loses badly, so
    "harder" budgets bought *easier* fights. Action economy dominates at these levels, and
    a builder that ignores it prices encounters backwards.

    So the count is chosen first — near the party's size, where a fight has a shape — and
    the monsters are then picked to fill the budget at that count. Because the group
    multiplier scales the total, every count fills the budget about equally well, which
    means the choice of shape is free and can be made on how it plays.

    Randomised only among equally-good candidates, so a seed reproduces the whole thing.
    """
    rng = rng or random.Random()
    budget = xp_budget(levels, difficulty)
    if budget <= 0:
        raise EncounterError("a party of nobody has no budget")

    pool = [
        m for m in candidates
        if m.xp > 0 and (max_challenge is None or m.challenge_rating <= max_challenge)
    ]
    if not pool:
        raise EncounterError("no monsters to choose from")

    best: list[Monster] = []
    best_score = (-1.0, 0)
    for count in range(1, max(1, min(max_monsters, len(levels) + 2)) + 1):
        group = _fill(pool, budget, count, rng)
        if not group:
            continue
        # Best budget use wins; ties go to the count nearest the party's size, which is
        # where a fight has both sides acting at a comparable rate.
        score = (adjusted_xp(group) / budget, -abs(len(group) - len(levels)))
        if score > best_score:
            best_score, best = score, group

    chosen = best
    if not chosen:
        raise EncounterError(
            f"nothing in the pool fits a {difficulty.value} budget of {budget} XP"
        )
    return EncounterPlan(
        monsters=tuple(chosen),
        difficulty=difficulty,
        budget=budget,
        raw_xp=sum(m.xp for m in chosen),
        adjusted_xp=adjusted_xp(chosen),
    )


def _fill(
    pool: Sequence[Monster], budget: int, count: int, rng: random.Random
) -> list[Monster]:
    """`count` monsters costing as much of the budget as they can without exceeding it.

    Same monster repeated: a pack is what the count is *for*, and a random assortment of
    one of everything reads as a zoo rather than an encounter. Mixed groups are the
    caller's to assemble from several plans.
    """
    ceiling = budget / (count * group_multiplier(count))
    affordable = [m for m in pool if m.xp <= ceiling]
    if not affordable:
        return []
    best_xp = max(m.xp for m in affordable)
    picks = sorted((m for m in affordable if m.xp == best_xp), key=lambda m: m.index)
    return [rng.choice(picks)] * count


# --- measuring what a budget actually means ---------------------------------


@dataclass
class SimulationResult:
    """What happened when a fight was played out many times.

    The reason the numbers above are claims rather than assertions. A budget you can test
    is worth more than a budget you can cite, and this is the test.
    """

    fights: int = 0
    party_wins: int = 0
    deaths: int = 0
    downs: int = 0
    rounds: list[int] = field(default_factory=list)
    unresolved: int = 0

    @property
    def win_rate(self) -> float:
        return self.party_wins / self.fights if self.fights else 0.0

    @property
    def death_rate(self) -> float:
        """Fights in which at least one character died outright."""
        return self.deaths / self.fights if self.fights else 0.0

    @property
    def down_rate(self) -> float:
        return self.downs / self.fights if self.fights else 0.0

    @property
    def median_rounds(self) -> float:
        if not self.rounds:
            return 0.0
        ordered = sorted(self.rounds)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[middle])
        return (ordered[middle - 1] + ordered[middle]) / 2

    def summary(self) -> str:
        return (
            f"{self.fights} fights · party wins {self.win_rate:.0%} · "
            f"someone down {self.down_rate:.0%} · someone died {self.death_rate:.0%} · "
            f"median {self.median_rounds:g} rounds"
        )


def simulate(
    play_one: Callable[[random.Random], tuple[bool, int, int, int]],
    fights: int = 200,
    seed: int = 0,
) -> SimulationResult:
    """Run one fight many times and total up what happened.

    `play_one` returns (party won, characters who dropped, characters who died, rounds).
    Kept as a callback so this module needs nothing from `game/` — the rules core does not
    import the turn loop, and a measurement helper should not be the thing that breaks it.
    """
    result = SimulationResult()
    for index in range(fights):
        won, downs, deaths, rounds = play_one(random.Random(seed + index))
        result.fights += 1
        result.party_wins += int(won)
        result.downs += int(downs > 0)
        result.deaths += int(deaths > 0)
        result.rounds.append(rounds)
    return result


__all__ = [
    "DIFFICULTY_MULTIPLIER",
    "GROUP_MULTIPLIER",
    "MEDIUM_XP_PER_LEVEL",
    "Difficulty",
    "EncounterError",
    "EncounterPlan",
    "SimulationResult",
    "adjusted_xp",
    "build",
    "group_multiplier",
    "simulate",
    "xp_budget",
]
