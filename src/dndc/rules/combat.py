"""The deterministic combat core (P3.1) — every number in a fight.

D-001 says the engine owns mechanics and the GM narrates what it is handed. Combat is
where that stops being a principle and starts being most of the code: initiative, hits,
damage, hit points, unconsciousness and death are all decided here, and none of it is ever
a model's to compute. The GM's part of a fight arrives in P3.4 and receives outcomes, not
inputs.

**Nothing in this module logs, calls a model, or touches disk.** State in, new state out,
same as the rest of `rules/`. That is what makes a fight reproducible from a seed, which
is what makes it auditable at all.

Two decisions worth stating, because both had a tempting easier answer:

**Initiative ties break deterministically.** 5e leaves them to the DM, which is fine at a
table and useless in an instrument: the same seed and the same combatants must produce the
same order every time or a replayed fight is not the fight that happened. Ties go to the
higher Dexterity, then to the side (the party first, which is the common table courtesy),
then to the name. No dice are re-rolled and nothing is random about the resolution.

**A combatant at 0 HP is not "dead" here.** Player characters fall unconscious and make
death saves; monsters simply drop. Collapsing those would be simpler and would quietly
delete the most tense thirty seconds in 5e, so the distinction is a field on the combatant
rather than a rule in the caller.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Sequence

from dndc.rules.checks import Advantage
from dndc.rules.dice import D20Result, roll_d20

#: 5e: three successes stabilise, three failures kill. A natural 20 restores 1 HP; a
#: natural 1 counts as two failures.
DEATH_SAVE_DC = 10
DEATH_SAVES_NEEDED = 3


class Side(str, Enum):
    """Who a combatant fights for. Two sides is enough for a home table."""

    PARTY = "party"
    FOES = "foes"


class Condition(str, Enum):
    """The conditions the combat core acts on. Others are narrative until they are not."""

    UNCONSCIOUS = "unconscious"
    DEAD = "dead"
    STABLE = "stable"
    PRONE = "prone"
    GRAPPLED = "grappled"
    RESTRAINED = "restrained"
    INCAPACITATED = "incapacitated"


class DamageEffect(str, Enum):
    """How a combatant's body answers a damage type."""

    NORMAL = "normal"
    RESISTANT = "resistant"
    VULNERABLE = "vulnerable"
    IMMUNE = "immune"


@dataclass(frozen=True)
class DeathSaves:
    """A dying character's tally. Frozen: every change is a new one, so a fight replays."""

    successes: int = 0
    failures: int = 0

    @property
    def stabilised(self) -> bool:
        return self.successes >= DEATH_SAVES_NEEDED

    @property
    def dead(self) -> bool:
        return self.failures >= DEATH_SAVES_NEEDED


@dataclass(frozen=True)
class Combatant:
    """One participant. Frozen — `apply_damage` and friends return a new one.

    Immutability is not stylistic here. A fight is a sequence of states, and being able to
    hold two of them at once is what lets a caller show "before and after" without
    bookkeeping, and what stops a half-applied turn from existing at all.
    """

    id: str
    name: str
    side: Side
    max_hp: int
    current_hp: int
    armor_class: int
    initiative_modifier: int = 0
    #: For initiative tie-breaks; defaults to the initiative modifier, which for most
    #: combatants *is* the Dexterity modifier.
    dexterity: int | None = None
    conditions: frozenset[Condition] = frozenset()
    death_saves: DeathSaves = DeathSaves()
    temporary_hp: int = 0
    #: Player characters fall unconscious at 0 and roll death saves. Monsters drop.
    is_player: bool = False
    resistances: frozenset[str] = frozenset()
    vulnerabilities: frozenset[str] = frozenset()
    immunities: frozenset[str] = frozenset()

    @property
    def tiebreak_dexterity(self) -> int:
        return self.dexterity if self.dexterity is not None else self.initiative_modifier

    @property
    def down(self) -> bool:
        """At zero and out of the fight, whether dying or dead."""
        return self.current_hp <= 0

    @property
    def dead(self) -> bool:
        return Condition.DEAD in self.conditions

    @property
    def dying(self) -> bool:
        """Down, not dead, not yet stable — the only state death saves happen in."""
        return (
            self.down
            and not self.dead
            and Condition.STABLE not in self.conditions
        )

    @property
    def acts(self) -> bool:
        """Can this combatant take a turn at all?"""
        return not self.down and Condition.INCAPACITATED not in self.conditions

    def effect_of(self, damage_type: str | None) -> DamageEffect:
        """Immunity beats vulnerability beats resistance — 5e's own precedence."""
        kind = (damage_type or "").strip().casefold()
        if not kind:
            return DamageEffect.NORMAL
        if kind in self.immunities:
            return DamageEffect.IMMUNE
        if kind in self.vulnerabilities and kind in self.resistances:
            # 5e: they cancel, and the result is neither.
            return DamageEffect.NORMAL
        if kind in self.vulnerabilities:
            return DamageEffect.VULNERABLE
        if kind in self.resistances:
            return DamageEffect.RESISTANT
        return DamageEffect.NORMAL

    def with_conditions(
        self, add: Iterable[Condition] = (), remove: Iterable[Condition] = ()
    ) -> Combatant:
        conditions = (self.conditions | frozenset(add)) - frozenset(remove)
        return replace(self, conditions=conditions)


@dataclass(frozen=True)
class DamageOutcome:
    """What one hit did. The numbers the interface renders (OD-11)."""

    combatant: Combatant
    rolled: int
    #: After resistance/vulnerability/immunity, before temporary hit points.
    effective: int
    absorbed: int
    #: What actually came off real hit points.
    taken: int
    effect: DamageEffect = DamageEffect.NORMAL
    dropped: bool = False
    killed: bool = False
    #: True when damage at 0 HP equalled or exceeded the maximum — instant death, no saves.
    massive: bool = False

    @property
    def overkill(self) -> int:
        return max(0, self.effective - self.absorbed - max(0, self.combatant.max_hp))


def apply_damage(
    combatant: Combatant, amount: int, damage_type: str | None = None
) -> DamageOutcome:
    """Take damage, in 5e's order: type effects, then temporary HP, then real HP.

    The massive-damage rule is here rather than left to the caller because it is the one
    place a character can die without a single death save, and a rule that lives in a
    caller is a rule that will be missing from the second caller.
    """
    rolled = max(0, int(amount))
    effect = combatant.effect_of(damage_type)

    if effect is DamageEffect.IMMUNE:
        effective = 0
    elif effect is DamageEffect.RESISTANT:
        effective = rolled // 2
    elif effect is DamageEffect.VULNERABLE:
        effective = rolled * 2
    else:
        effective = rolled

    absorbed = min(combatant.temporary_hp, effective)
    taken = effective - absorbed
    remaining = max(0, combatant.current_hp - taken)

    was_up = not combatant.down
    updated = replace(
        combatant,
        current_hp=remaining,
        temporary_hp=combatant.temporary_hp - absorbed,
    )

    # Damage that carries past zero by the character's whole maximum kills outright.
    excess = taken - combatant.current_hp
    massive = remaining == 0 and excess >= combatant.max_hp
    killed = False

    if remaining == 0:
        if massive or not combatant.is_player:
            updated = updated.with_conditions(
                add=(Condition.DEAD, Condition.UNCONSCIOUS), remove=(Condition.STABLE,)
            )
            killed = True
        else:
            # A hit on a dying character is itself a failed death save (two on a crit,
            # which the caller applies through `record_death_save`).
            updated = updated.with_conditions(
                add=(Condition.UNCONSCIOUS,), remove=(Condition.STABLE,)
            )
            if not was_up:
                updated = replace(
                    updated,
                    death_saves=DeathSaves(
                        successes=combatant.death_saves.successes,
                        failures=min(
                            DEATH_SAVES_NEEDED, combatant.death_saves.failures + 1
                        ),
                    ),
                )
                if updated.death_saves.dead:
                    updated = updated.with_conditions(add=(Condition.DEAD,))
                    killed = True

    return DamageOutcome(
        combatant=updated,
        rolled=rolled,
        effective=effective,
        absorbed=absorbed,
        taken=taken,
        effect=effect,
        dropped=was_up and remaining == 0,
        killed=killed,
        massive=massive,
    )


def heal(combatant: Combatant, amount: int) -> Combatant:
    """Restore hit points. Healing a dying character wakes them; it cannot raise the dead."""
    if combatant.dead:
        return combatant
    restored = min(combatant.max_hp, combatant.current_hp + max(0, int(amount)))
    updated = replace(combatant, current_hp=restored, death_saves=DeathSaves())
    if restored > 0:
        updated = updated.with_conditions(
            remove=(Condition.UNCONSCIOUS, Condition.STABLE)
        )
    return updated


@dataclass(frozen=True)
class DeathSaveResult:
    combatant: Combatant
    roll: D20Result
    success: bool
    critical: bool = False
    stabilised: bool = False
    died: bool = False
    #: A natural 20 puts the character back on their feet at 1 HP.
    revived: bool = False


def record_death_save(
    rng: random.Random, combatant: Combatant, advantage: Advantage = Advantage.NORMAL
) -> DeathSaveResult:
    """One death saving throw. DC 10, flat — no modifier, no proficiency (5e).

    A natural 20 is not a success but a recovery: the character wakes at 1 HP. A natural 1
    counts twice. Both are the rule, and both are the reason this is not a plain check.
    """
    result = roll_d20(rng, modifier=0, advantage=advantage)
    natural = result.natural

    if natural == 20:
        return DeathSaveResult(
            combatant=heal(combatant, 1),
            roll=result,
            success=True,
            critical=True,
            revived=True,
        )

    saves = combatant.death_saves
    if natural == 1:
        saves = DeathSaves(saves.successes, min(DEATH_SAVES_NEEDED, saves.failures + 2))
    elif result.total >= DEATH_SAVE_DC:
        saves = DeathSaves(min(DEATH_SAVES_NEEDED, saves.successes + 1), saves.failures)
    else:
        saves = DeathSaves(saves.successes, min(DEATH_SAVES_NEEDED, saves.failures + 1))

    updated = replace(combatant, death_saves=saves)
    if saves.dead:
        updated = updated.with_conditions(add=(Condition.DEAD,))
    elif saves.stabilised:
        updated = updated.with_conditions(add=(Condition.STABLE,))

    return DeathSaveResult(
        combatant=updated,
        roll=result,
        success=natural != 1 and result.total >= DEATH_SAVE_DC,
        critical=natural == 1,
        stabilised=saves.stabilised and not saves.dead,
        died=saves.dead,
    )


# --- initiative and turn order ----------------------------------------------


@dataclass(frozen=True)
class InitiativeEntry:
    combatant_id: str
    roll: D20Result
    total: int
    #: What settled a tie, for the log and for anyone asking why. Empty when nothing did.
    tiebreak: str = ""


def roll_initiative(
    rng: random.Random, combatants: Sequence[Combatant]
) -> list[InitiativeEntry]:
    """Roll initiative for everyone, highest first, ties broken reproducibly.

    5e hands ties to the DM. That is fine at a table and useless in an instrument: the
    same seed and the same combatants have to produce the same order, or a replayed fight
    is not the fight that happened. So ties fall to Dexterity, then to the party, then to
    the name — none of which re-rolls a die.
    """
    rolled = [
        (combatant, roll_d20(rng, modifier=combatant.initiative_modifier))
        for combatant in combatants
    ]

    def key(pair: tuple[Combatant, D20Result]):
        combatant, result = pair
        return (
            -result.total,
            -combatant.tiebreak_dexterity,
            0 if combatant.side is Side.PARTY else 1,
            combatant.name.casefold(),
        )

    ordered = sorted(rolled, key=key)
    entries = []
    for index, (combatant, result) in enumerate(ordered):
        tiebreak = ""
        if index and ordered[index - 1][1].total == result.total:
            previous = ordered[index - 1][0]
            if previous.tiebreak_dexterity != combatant.tiebreak_dexterity:
                tiebreak = "dexterity"
            elif previous.side is not combatant.side:
                tiebreak = "side"
            else:
                tiebreak = "name"
        entries.append(
            InitiativeEntry(
                combatant_id=combatant.id,
                roll=result,
                total=result.total,
                tiebreak=tiebreak,
            )
        )
    return entries


@dataclass(frozen=True)
class TurnBudget:
    """5e's action economy for one turn. Spent, never refunded — a new turn is a new one."""

    action: bool = True
    bonus_action: bool = True
    reaction: bool = True
    movement: int = 30

    def spend_action(self) -> TurnBudget:
        return replace(self, action=False)

    def spend_bonus_action(self) -> TurnBudget:
        return replace(self, bonus_action=False)

    def spend_reaction(self) -> TurnBudget:
        return replace(self, reaction=False)

    def move(self, feet: int) -> TurnBudget:
        """Movement is clamped at zero rather than refused: a caller asking to move
        further than the budget allows has made a mistake worth seeing in the numbers,
        not one worth raising over mid-fight."""
        return replace(self, movement=max(0, self.movement - max(0, int(feet))))


class CombatError(RuntimeError):
    """A combat operation that cannot mean anything — an unknown combatant, mostly."""


@dataclass
class Encounter:
    """A fight in progress: who is in it, in what order, and whose turn it is.

    The one mutable thing in this module, because a fight *is* a sequence of mutations and
    threading it through pure calls would put the bookkeeping in every caller. Every
    combatant inside it is still frozen, so no state is ever half-changed.
    """

    combatants: dict[str, Combatant] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    round: int = 0
    turn_index: int = 0
    budget: TurnBudget = TurnBudget()
    initiative: list[InitiativeEntry] = field(default_factory=list)

    @classmethod
    def start(
        cls, rng: random.Random, combatants: Sequence[Combatant]
    ) -> Encounter:
        """Roll initiative and open round one."""
        if not combatants:
            raise CombatError("an encounter needs at least one combatant")
        entries = roll_initiative(rng, combatants)
        encounter = cls(
            combatants={c.id: c for c in combatants},
            order=[entry.combatant_id for entry in entries],
            round=1,
            turn_index=0,
            initiative=entries,
        )
        encounter.budget = encounter._budget_for(encounter.active)
        return encounter

    # --- reads -------------------------------------------------------------

    @property
    def active(self) -> Combatant:
        """Whose turn it is."""
        return self.combatants[self.order[self.turn_index]]

    @property
    def over(self) -> bool:
        """One side has nobody left standing."""
        return not (self.standing(Side.PARTY) and self.standing(Side.FOES))

    @property
    def winner(self) -> Side | None:
        if not self.over:
            return None
        if self.standing(Side.PARTY):
            return Side.PARTY
        if self.standing(Side.FOES):
            return Side.FOES
        return None

    def standing(self, side: Side) -> list[Combatant]:
        return [c for c in self.combatants.values() if c.side is side and not c.down]

    def get(self, combatant_id: str) -> Combatant:
        try:
            return self.combatants[combatant_id]
        except KeyError:
            raise CombatError(f"no combatant {combatant_id!r} in this encounter") from None

    def in_order(self) -> list[Combatant]:
        return [self.combatants[cid] for cid in self.order]

    # --- writes ------------------------------------------------------------

    def replace_combatant(self, combatant: Combatant) -> Combatant:
        """Put an updated combatant back. The only way state changes.

        Being the one choke point is what makes the next two lines safe to write once: a
        combatant dropped *during their own turn* — by a reaction, a trap, ongoing damage
        — has to lose what is left of their action economy, and doing that here means no
        caller can forget it. Healing does not hand the turn back; the next one brings a
        fresh budget anyway.
        """
        self.get(combatant.id)
        self.combatants[combatant.id] = combatant
        if combatant.id == self.order[self.turn_index] and not combatant.acts:
            self.budget = self._budget_for(combatant)
        return combatant

    def damage(
        self, combatant_id: str, amount: int, damage_type: str | None = None
    ) -> DamageOutcome:
        outcome = apply_damage(self.get(combatant_id), amount, damage_type)
        self.replace_combatant(outcome.combatant)
        return outcome

    def heal(self, combatant_id: str, amount: int) -> Combatant:
        return self.replace_combatant(heal(self.get(combatant_id), amount))

    def death_save(
        self, combatant_id: str, rng: random.Random, advantage: Advantage = Advantage.NORMAL
    ) -> DeathSaveResult:
        result = record_death_save(rng, self.get(combatant_id), advantage)
        self.replace_combatant(result.combatant)
        return result

    def advance(self) -> Combatant:
        """Hand the turn on, rolling into the next round at the end of the order.

        Combatants who cannot act are skipped rather than asked, but a *dying* one is not:
        their turn is when the death save happens, and skipping them would quietly remove
        the clock from the most tense part of the game.
        """
        for _ in range(len(self.order)):
            self.turn_index += 1
            if self.turn_index >= len(self.order):
                self.turn_index = 0
                self.round += 1
            combatant = self.active
            if combatant.acts or combatant.dying:
                self.budget = self._budget_for(combatant)
                return combatant
        # Nobody left who can do anything. Stay put rather than spin.
        self.budget = self._budget_for(self.active)
        return self.active

    def _budget_for(self, combatant: Combatant) -> TurnBudget:
        if not combatant.acts:
            return TurnBudget(action=False, bonus_action=False, reaction=False, movement=0)
        return TurnBudget()


__all__ = [
    "DEATH_SAVES_NEEDED",
    "DEATH_SAVE_DC",
    "Combatant",
    "CombatError",
    "Condition",
    "DamageEffect",
    "DamageOutcome",
    "DeathSaveResult",
    "DeathSaves",
    "Encounter",
    "InitiativeEntry",
    "Side",
    "TurnBudget",
    "apply_damage",
    "heal",
    "record_death_save",
    "roll_initiative",
]
