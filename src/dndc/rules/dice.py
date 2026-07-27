"""Dice expression parsing and rolling.

Pure functions over an explicit `random.Random`, so every roll in a session is
reproducible from the seed recorded in `session_meta` (D-008). Nothing here
imports a model or touches the network (D-001).

Grammar (case-insensitive, whitespace ignored)::

    expr    := term (('+' | '-') term)*
    term    := dice | integer
    dice    := [count] 'd' sides [modifier]
    modifier:= 'kh'N | 'kl'N | 'dh'N | 'dl'N     # keep/drop highest/lowest

`kh`/`kl` keep the N highest/lowest dice; `dh`/`dl` drop them. Advantage is
`2d20kh1` and disadvantage is `2d20kl1`, but prefer `roll_d20` for checks —
it names the intent and emits a cleaner result.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from enum import Enum

MAX_DICE = 1000
MAX_SIDES = 1000


class DiceError(ValueError):
    """Raised for a malformed or out-of-bounds dice expression."""


class Advantage(str, Enum):
    """How a d20 roll is made."""

    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class DiceGroup:
    """One `NdS` term with its keep/drop modifier, as parsed."""

    count: int
    sides: int
    keep_highest: int | None = None
    keep_lowest: int | None = None
    sign: int = 1

    def notation(self) -> str:
        body = f"{self.count}d{self.sides}"
        if self.keep_highest is not None:
            body += f"kh{self.keep_highest}"
        elif self.keep_lowest is not None:
            body += f"kl{self.keep_lowest}"
        return body


@dataclass(frozen=True)
class GroupResult:
    """What one dice group actually rolled."""

    group: DiceGroup
    rolls: tuple[int, ...]
    kept: tuple[int, ...]
    subtotal: int


@dataclass(frozen=True)
class RollResult:
    """The full outcome of one dice expression — reproducible and loggable."""

    expression: str
    total: int
    groups: tuple[GroupResult, ...] = field(default_factory=tuple)
    constant: int = 0

    @property
    def all_rolls(self) -> tuple[int, ...]:
        return tuple(r for g in self.groups for r in g.rolls)


_TOKEN_RE = re.compile(
    r"""
    \s* (?P<sign>[+-])? \s*
    (?:
        (?P<count>\d*)d(?P<sides>\d+)
        (?:(?P<mod>kh|kl|dh|dl)(?P<modn>\d+))?
      | (?P<const>\d+)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse(expression: str) -> tuple[tuple[DiceGroup, ...], int]:
    """Parse a dice expression into its groups and flat constant.

    Returns (groups, constant). Raises `DiceError` on anything malformed —
    a silent misparse would corrupt the mechanics the GM narrates.
    """
    # Only outer whitespace is stripped. Interior whitespace is significant: it
    # must not be able to fuse two terms, or "2d6 3" would silently parse as 2d63.
    cleaned = expression.strip()
    if not cleaned:
        raise DiceError("empty dice expression")

    groups: list[DiceGroup] = []
    constant = 0
    pos = 0
    seen_term = False

    while pos < len(cleaned):
        match = _TOKEN_RE.match(cleaned, pos)
        if match is None or match.end() == pos:
            raise DiceError(f"could not parse {expression!r} at offset {pos}")
        if seen_term and match.group("sign") is None:
            raise DiceError(f"missing operator in {expression!r} at offset {pos}")

        sign = -1 if match.group("sign") == "-" else 1

        if match.group("const") is not None:
            constant += sign * int(match.group("const"))
        else:
            count = int(match.group("count") or 1)
            sides = int(match.group("sides"))
            if count < 1:
                raise DiceError(f"dice count must be >= 1 in {expression!r}")
            if count > MAX_DICE:
                raise DiceError(f"dice count {count} exceeds limit {MAX_DICE}")
            if sides < 2:
                raise DiceError(f"a die needs at least 2 sides in {expression!r}")
            if sides > MAX_SIDES:
                raise DiceError(f"die size {sides} exceeds limit {MAX_SIDES}")

            keep_highest = keep_lowest = None
            mod = match.group("mod")
            if mod is not None:
                modn = int(match.group("modn"))
                mod = mod.lower()
                if modn < 0:
                    raise DiceError(f"modifier count must be >= 0 in {expression!r}")
                if mod in ("kh", "kl") and modn > count:
                    raise DiceError(f"cannot keep {modn} of {count} dice in {expression!r}")
                if mod in ("dh", "dl") and modn >= count:
                    raise DiceError(f"cannot drop {modn} of {count} dice in {expression!r}")
                if mod == "kh":
                    keep_highest = modn
                elif mod == "kl":
                    keep_lowest = modn
                elif mod == "dh":
                    keep_lowest = count - modn
                else:  # dl
                    keep_highest = count - modn

            groups.append(
                DiceGroup(
                    count=count,
                    sides=sides,
                    keep_highest=keep_highest,
                    keep_lowest=keep_lowest,
                    sign=sign,
                )
            )

        seen_term = True
        pos = match.end()

    return tuple(groups), constant


def _select(rolls: tuple[int, ...], group: DiceGroup) -> tuple[int, ...]:
    """Apply the group's keep/drop modifier, preserving roll order in the output."""
    if group.keep_highest is None and group.keep_lowest is None:
        return rolls
    n = group.keep_highest if group.keep_highest is not None else group.keep_lowest
    if n == 0:
        return ()
    # Rank by value, breaking ties by original index so selection is deterministic.
    order = sorted(range(len(rolls)), key=lambda i: (rolls[i], i))
    chosen = set(order[-n:] if group.keep_highest is not None else order[:n])
    return tuple(rolls[i] for i in sorted(chosen))


def roll(expression: str, rng: random.Random) -> RollResult:
    """Roll a dice expression. `rng` is required — no implicit global randomness."""
    groups, constant = parse(expression)
    results: list[GroupResult] = []
    total = constant

    for group in groups:
        rolls = tuple(rng.randint(1, group.sides) for _ in range(group.count))
        kept = _select(rolls, group)
        subtotal = group.sign * sum(kept)
        total += subtotal
        results.append(GroupResult(group=group, rolls=rolls, kept=kept, subtotal=subtotal))

    return RollResult(
        expression=expression,
        total=total,
        groups=tuple(results),
        constant=constant,
    )


@dataclass(frozen=True)
class D20Result:
    """A d20 roll with its advantage state — the shape checks and attacks consume."""

    rolls: tuple[int, ...]
    natural: int
    modifier: int
    total: int
    advantage: Advantage

    @property
    def is_natural_20(self) -> bool:
        return self.natural == 20

    @property
    def is_natural_1(self) -> bool:
        return self.natural == 1


def roll_d20(
    rng: random.Random,
    modifier: int = 0,
    advantage: Advantage = Advantage.NORMAL,
) -> D20Result:
    """Roll a d20 with the given modifier and advantage state.

    Advantage and disadvantage both roll two dice; which one counts depends on
    the state. They do not stack in 5e — a single call carries the net state,
    and the caller is responsible for cancelling them out first.
    """
    n = 1 if advantage is Advantage.NORMAL else 2
    rolls = tuple(rng.randint(1, 20) for _ in range(n))
    if advantage is Advantage.ADVANTAGE:
        natural = max(rolls)
    elif advantage is Advantage.DISADVANTAGE:
        natural = min(rolls)
    else:
        natural = rolls[0]
    return D20Result(
        rolls=rolls,
        natural=natural,
        modifier=modifier,
        total=natural + modifier,
        advantage=advantage,
    )


def net_advantage(has_advantage: bool, has_disadvantage: bool) -> Advantage:
    """5e rule: any advantage plus any disadvantage cancels to a normal roll."""
    if has_advantage and not has_disadvantage:
        return Advantage.ADVANTAGE
    if has_disadvantage and not has_advantage:
        return Advantage.DISADVANTAGE
    return Advantage.NORMAL
