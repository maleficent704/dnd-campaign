"""Recording a fight as events (P3.3).

`rules/combat.py` is pure and stays that way — it cannot log, and that is what makes a
fight reproducible from a seed. This is the other half: the thing that watches an
`Encounter` and writes the D-008 rows for it.

The vocabulary was amended on 2026-08-20 and this module is how that amendment was
checked. A vocabulary nothing has ever emitted is a guess about the game; a test here
plays a fight and reads its own log back, which is the difference between a schema that
compiles and one that describes what happened.

**Two rows for one hit, deliberately.** An attack writes a `rules_resolution` (the dice,
the AC, the hit) and a `hit_point_change` (what it did to the target), linked by
`resolution_seq`. They come apart in real play — a fall damages with no attack roll, and
resistance changes what a roll means without changing the roll — so collapsing them would
lose the distinction exactly when it mattered.

Nothing here decides anything. Every number it writes was computed by the rules core and
handed over; the recorder's only judgement is which row a thing belongs in.
"""

from __future__ import annotations

from typing import Sequence

from dndc.logging import SessionLog
from dndc.rules.checks import AttackResult
from dndc.rules.combat import (
    Combatant,
    DamageOutcome,
    DeathSaveResult,
    Encounter,
    Side,
)
from dndc.schema.events import (
    CombatantRecord,
    CombatEnd,
    CombatOutcome,
    CombatSide,
    CombatStart,
    CombatTurn,
    DamageEffect,
    DiceRoll,
    HitPointChange,
    RulesResolution,
)

#: `rules_resolution.kind` values a fight produces. The field was specified with these
#: names in the original D-008 (2026-07-27), which is why combat added no family for them.
ATTACK = "attack"
DEATH_SAVE = "save"
INITIATIVE = "initiative"


class CombatRecorder:
    """Writes the D-008 rows for one encounter. A `None` log makes every call a no-op,
    so a fight can be run in a test or a scratch script without a session."""

    def __init__(self, encounter_id: str, log: SessionLog | None = None) -> None:
        self.encounter_id = encounter_id
        self.log = log

    # --- the fight's shape --------------------------------------------------

    def started(self, encounter: Encounter, seed: int | None = None) -> int | None:
        """The roster as instantiated, and the order.

        Load-bearing for replay: monster hit points may be rolled (P3.2), so without this
        row every later event in the fight refers to a creature of unknown durability.
        """
        return self._emit(
            CombatStart,
            combatants=tuple(_record(c) for c in encounter.in_order()),
            order=tuple(encounter.order),
            seed=seed,
            round=encounter.round,
        )

    def turn(self, encounter: Encounter) -> int | None:
        return self._emit(
            CombatTurn, round=encounter.round, combatant=encounter.active.id
        )

    def ended(self, encounter: Encounter) -> int | None:
        return self._emit(
            CombatEnd,
            outcome=_outcome(encounter),
            rounds=encounter.round,
            survivors=tuple(
                c.id for c in encounter.combatants.values() if not c.down
            ),
        )

    # --- what happens in it -------------------------------------------------

    def attack(
        self,
        actor: Combatant,
        target: Combatant,
        result: AttackResult,
        seed: int | None = None,
    ) -> int | None:
        """The attack roll. A target's AC is the DC it was rolled against."""
        return self._emit_resolution(
            kind=ATTACK,
            actor=actor.id,
            target=target.id,
            dc=result.target_ac,
            advantage=result.roll.advantage.value,
            roll=_dice(result),
            success=result.hit,
            critical=result.critical,
            seed=seed,
        )

    def death_save(
        self, combatant: Combatant, result: DeathSaveResult, seed: int | None = None
    ) -> int | None:
        """A death save is a save against DC 10 with no ability and no proficiency —
        which is exactly what the rules say it is, so it needs no family of its own."""
        from dndc.rules.combat import DEATH_SAVE_DC

        return self._emit_resolution(
            kind=DEATH_SAVE,
            actor=combatant.id,
            dc=DEATH_SAVE_DC,
            advantage=result.roll.advantage.value,
            roll=DiceRoll(
                expression="1d20",
                rolls=tuple(result.roll.rolls),
                kept=(result.roll.natural,),
                modifier=0,
                total=result.roll.total,
            ),
            success=result.success,
            seed=seed,
            detail={
                "successes": result.combatant.death_saves.successes,
                "failures": result.combatant.death_saves.failures,
                "revived": result.revived,
                "stabilised": result.stabilised,
                "died": result.died,
            },
        )

    def hit_points(
        self,
        before: Combatant,
        outcome: DamageOutcome,
        resolution_seq: int | None = None,
    ) -> int | None:
        """What the hit did to the sheet, as distinct from the dice that rolled it.

        `amount` is what actually came off hit points — `before - after` — and not
        `outcome.taken`, which is the damage applied before the floor at zero. A 31-point
        hit on a character with 24 left takes 24; a row saying otherwise disagrees with
        its own `before` and `after`, and a self-inconsistent row is worse than a missing
        one. The excess is still recoverable from the damage roll.
        """
        return self._emit(
            HitPointChange,
            combatant=before.id,
            before=before.current_hp,
            after=outcome.combatant.current_hp,
            amount=before.current_hp - outcome.combatant.current_hp,
            damage_type=outcome.damage_type,
            effect=DamageEffect(outcome.effect.value),
            temporary_absorbed=outcome.absorbed,
            dropped=outcome.dropped,
            killed=outcome.killed,
            resolution_seq=resolution_seq,
        )

    def healed(
        self, before: Combatant, after: Combatant, resolution_seq: int | None = None
    ) -> int | None:
        """Healing is the same row with a negative amount, so summing `amount` over a
        fight gives net damage without a caller having to know two shapes."""
        return self._emit(
            HitPointChange,
            combatant=before.id,
            before=before.current_hp,
            after=after.current_hp,
            amount=-(after.current_hp - before.current_hp),
            resolution_seq=resolution_seq,
        )

    # --- plumbing -----------------------------------------------------------

    def _emit(self, event_type, **fields) -> int | None:
        if self.log is None:
            return None
        return self.log.emit(event_type, encounter_id=self.encounter_id, **fields).seq

    def _emit_resolution(self, **fields) -> int | None:
        """`rules_resolution` is shared with every check in the game and takes no
        `encounter_id`; which fight a roll belongs to rides in `detail` instead, where
        the per-kind extras go (D-008, amended 2026-08-20)."""
        if self.log is None:
            return None
        detail = {"encounter": self.encounter_id, **fields.pop("detail", {})}
        return self.log.emit(RulesResolution, detail=detail, **fields).seq


def _record(combatant: Combatant) -> CombatantRecord:
    return CombatantRecord(
        id=combatant.id,
        name=combatant.name,
        side=CombatSide(combatant.side.value),
        max_hp=combatant.max_hp,
        current_hp=combatant.current_hp,
        armor_class=combatant.armor_class,
        is_player=combatant.is_player,
    )


def _dice(result: AttackResult) -> DiceRoll:
    return DiceRoll(
        expression="1d20",
        rolls=tuple(result.roll.rolls),
        # `rolls` holds both dice under advantage; `natural` is the one kept.
        kept=(result.roll.natural,),
        modifier=result.roll.modifier,
        total=result.roll.total,
    )


def _outcome(encounter: Encounter) -> CombatOutcome:
    winner = encounter.winner
    if winner is Side.PARTY:
        return CombatOutcome.PARTY
    if winner is Side.FOES:
        return CombatOutcome.FOES
    return CombatOutcome.DRAW


def damage_taken(events: Sequence[object]) -> dict[str, int]:
    """Net hit points lost per combatant, over any run of events.

    Here rather than in `analysis/` because it is the shape of the row rather than a
    finding about a campaign — and because it is the cheapest possible check that the
    vocabulary is usable: if summing a fight's damage is awkward, the row is wrong.
    """
    totals: dict[str, int] = {}
    for event in events:
        if isinstance(event, HitPointChange):
            totals[event.combatant] = totals.get(event.combatant, 0) + event.amount
    return totals


__all__ = ["ATTACK", "DEATH_SAVE", "INITIATIVE", "CombatRecorder", "damage_taken"]
