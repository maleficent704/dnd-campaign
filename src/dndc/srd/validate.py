"""Referential integrity checks over the normalized SRD dataset.

Pydantic proves each record is *well-formed*; this proves the collections agree with
each other. A spell that lists a class we do not have, or a species pointing at a
missing subspecies, would surface at runtime as a GM hallucination rather than as a
crash — which is exactly the failure mode D-001 exists to keep out of the model's lap.

Returns issues rather than raising: a partial dataset is still usable, and the CLI
should be able to show every problem at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndc.rules import dice
from dndc.schema.srd import SRDData

#: Collections that must never be empty — an empty one means ingestion silently failed.
REQUIRED_NON_EMPTY = ("species", "classes", "spells", "monsters", "equipment", "conditions")


@dataclass(frozen=True)
class ValidationIssue:
    collection: str
    index: str
    problem: str

    def __str__(self) -> str:
        return f"{self.collection}/{self.index}: {self.problem}"


def _dice_issues(data: SRDData) -> list[ValidationIssue]:
    """Every dice expression in the dataset must parse in the P0.3 engine.

    Upstream mixes rollable expressions with symbolic placeholders — "1d8 + MOD" for the
    caster's ability modifier is the known case, handled during ingestion. Anything else
    of that kind must surface here, at ingest time, rather than as a DiceError thrown at
    the table mid-session.
    """
    issues: list[ValidationIssue] = []

    def check(collection: str, index: str, expression: str, label: str) -> None:
        if not expression:
            return
        try:
            dice.parse(expression)
        except dice.DiceError as exc:
            issues.append(
                ValidationIssue(collection, index, f"unrollable {label} {expression!r}: {exc}")
            )

    for index, spell in data.spells.items():
        if spell.damage:
            for level, expression in spell.damage.at_slot_level.items():
                check("spells", index, expression, f"damage at slot {level}")
            for level, expression in spell.damage.at_character_level.items():
                check("spells", index, expression, f"damage at character level {level}")
        for level, expression in spell.heal_at_slot_level.items():
            check("spells", index, expression, f"healing at slot {level}")

    for index, monster in data.monsters.items():
        check("monsters", index, monster.hit_dice, "hit dice")
        for group in (
            monster.actions,
            monster.special_abilities,
            monster.legendary_actions,
            monster.reactions,
        ):
            for action in group:
                for damage in action.damage:
                    check("monsters", index, damage.damage_dice, f"{action.name} damage")

    for index, item in data.equipment.items():
        if item.weapon:
            check("equipment", index, item.weapon.damage_dice, "weapon damage")
            check("equipment", index, item.weapon.two_handed_damage_dice or "", "two-handed damage")

    return issues


def validate_dataset(data: SRDData) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    counts = data.counts()

    for collection in REQUIRED_NON_EMPTY:
        if counts[collection] == 0:
            issues.append(ValidationIssue(collection, "*", "collection is empty"))

    for index, species in data.species.items():
        for sub in species.subspecies:
            if sub not in data.subspecies:
                issues.append(ValidationIssue("species", index, f"unknown subspecies {sub!r}"))

    for index, sub in data.subspecies.items():
        if sub.species not in data.species:
            issues.append(
                ValidationIssue("subspecies", index, f"unknown parent species {sub.species!r}")
            )

    for index, character_class in data.classes.items():
        levels = sorted(character_class.levels)
        expected = list(range(1, data.scope.max_class_level + 1))
        if levels != expected:
            issues.append(
                ValidationIssue(
                    "classes",
                    index,
                    f"levels {levels} do not cover 1..{data.scope.max_class_level}",
                )
            )
        # A caster with no slots at any ingested level means the level merge dropped them.
        if character_class.spellcasting_ability is not None and not any(
            level.spell_slots or level.cantrips_known
            for level in character_class.levels.values()
        ):
            issues.append(
                ValidationIssue("classes", index, "spellcaster has no slots or cantrips")
            )

    for index, spell in data.spells.items():
        for class_index in spell.classes:
            if class_index not in data.classes:
                issues.append(
                    ValidationIssue("spells", index, f"unknown class {class_index!r}")
                )

    # A background's kit is referred to by equipment index, and a reference that does not
    # resolve is a character quietly starting a possession short.
    for index, background in data.backgrounds.items():
        for granted in background.equipment:
            if granted.index not in data.equipment:
                issues.append(
                    ValidationIssue(
                        "backgrounds", index, f"unknown equipment {granted.index!r}"
                    )
                )

    issues.extend(_dice_issues(data))

    for index, monster in data.monsters.items():
        for condition in monster.condition_immunities:
            if condition not in data.conditions:
                issues.append(
                    ValidationIssue("monsters", index, f"unknown condition {condition!r}")
                )
        if monster.challenge_rating > data.scope.max_challenge_rating:
            issues.append(
                ValidationIssue(
                    "monsters", index, f"CR {monster.challenge_rating} exceeds ingest scope"
                )
            )

    return issues
