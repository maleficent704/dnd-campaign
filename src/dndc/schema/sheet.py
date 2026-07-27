"""Character sheet schema.

The sheet is *data* (D-005): the co-creation conversation is the UX, this is the
output, and it round-trips to `campaigns/<name>/characters/*.yaml` so a player can
hand-edit it. Validation lives here so an invalid sheet can never reach the rules
engine or the GM prompt.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dndc.rules.checks import (
    Proficiency,
    ability_modifier,
    proficiency_bonus,
    proficiency_contribution,
)

MIN_LEVEL = 1
MAX_LEVEL = 20
MAX_SPELL_LEVEL = 9


class Ability(str, Enum):
    STR = "str"
    DEX = "dex"
    CON = "con"
    INT = "int"
    WIS = "wis"
    CHA = "cha"


class Skill(str, Enum):
    ACROBATICS = "acrobatics"
    ANIMAL_HANDLING = "animal_handling"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    DECEPTION = "deception"
    HISTORY = "history"
    INSIGHT = "insight"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    MEDICINE = "medicine"
    NATURE = "nature"
    PERCEPTION = "perception"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"
    RELIGION = "religion"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    SURVIVAL = "survival"


#: Which ability governs each skill. SRD 5e; fixed, not campaign-configurable.
SKILL_ABILITY: dict[Skill, Ability] = {
    Skill.ACROBATICS: Ability.DEX,
    Skill.ANIMAL_HANDLING: Ability.WIS,
    Skill.ARCANA: Ability.INT,
    Skill.ATHLETICS: Ability.STR,
    Skill.DECEPTION: Ability.CHA,
    Skill.HISTORY: Ability.INT,
    Skill.INSIGHT: Ability.WIS,
    Skill.INTIMIDATION: Ability.CHA,
    Skill.INVESTIGATION: Ability.INT,
    Skill.MEDICINE: Ability.WIS,
    Skill.NATURE: Ability.INT,
    Skill.PERCEPTION: Ability.WIS,
    Skill.PERFORMANCE: Ability.CHA,
    Skill.PERSUASION: Ability.CHA,
    Skill.RELIGION: Ability.INT,
    Skill.SLEIGHT_OF_HAND: Ability.DEX,
    Skill.STEALTH: Ability.DEX,
    Skill.SURVIVAL: Ability.WIS,
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class AbilityScores(_Model):
    """The six ability scores. 1..30 is the absolute 5e range."""

    str_: int = Field(ge=1, le=30, alias="str")
    dex: int = Field(ge=1, le=30)
    con: int = Field(ge=1, le=30)
    int_: int = Field(ge=1, le=30, alias="int")
    wis: int = Field(ge=1, le=30)
    cha: int = Field(ge=1, le=30)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def score(self, ability: Ability) -> int:
        return getattr(self, {"str": "str_", "int": "int_"}.get(ability.value, ability.value))

    def modifier(self, ability: Ability) -> int:
        return ability_modifier(self.score(ability))

    def as_dict(self) -> dict[Ability, int]:
        return {a: self.score(a) for a in Ability}


class HitPoints(_Model):
    maximum: int = Field(ge=1)
    current: int = Field(ge=0)
    temporary: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _current_within_maximum(self) -> Self:
        if self.current > self.maximum:
            raise ValueError(f"current HP {self.current} exceeds maximum {self.maximum}")
        return self


class SpellSlotLevel(_Model):
    total: int = Field(ge=0)
    expended: int = Field(default=0, ge=0)

    @property
    def available(self) -> int:
        return self.total - self.expended

    @model_validator(mode="after")
    def _expended_within_total(self) -> Self:
        if self.expended > self.total:
            raise ValueError(f"expended {self.expended} exceeds {self.total} slots")
        return self


class InventoryItem(_Model):
    name: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    weight: float = Field(default=0.0, ge=0)
    equipped: bool = False
    description: str | None = None


class Proficiencies(_Model):
    saving_throws: list[Ability] = Field(default_factory=list)
    skills: dict[Skill, Proficiency] = Field(default_factory=dict)
    armor: list[str] = Field(default_factory=list)
    weapons: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_saves(self) -> Self:
        if len(set(self.saving_throws)) != len(self.saving_throws):
            raise ValueError("duplicate saving throw proficiency")
        return self


class CharacterSheet(_Model):
    """A validated character. Derived values are computed, never stored."""

    name: str = Field(min_length=1)
    player: str = Field(min_length=1)
    species: str = Field(min_length=1)
    character_class: str = Field(min_length=1)
    level: int = Field(default=1, ge=MIN_LEVEL, le=MAX_LEVEL)
    background: str | None = None
    alignment: str | None = None

    abilities: AbilityScores
    proficiencies: Proficiencies = Field(default_factory=Proficiencies)
    hit_points: HitPoints
    armor_class: int = Field(ge=1)
    speed: int = Field(default=30, ge=0)
    hit_dice: str | None = None

    inventory: list[InventoryItem] = Field(default_factory=list)
    spell_slots: dict[int, SpellSlotLevel] = Field(default_factory=dict)
    spells_known: list[str] = Field(default_factory=list)

    backstory: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _spell_slot_levels_are_valid(self) -> Self:
        for lvl in self.spell_slots:
            if not 1 <= lvl <= MAX_SPELL_LEVEL:
                raise ValueError(f"spell slot level {lvl} outside 1..{MAX_SPELL_LEVEL}")
        return self

    # --- derived values ----------------------------------------------------

    @property
    def proficiency_bonus(self) -> int:
        return proficiency_bonus(self.level)

    def ability_modifier(self, ability: Ability) -> int:
        return self.abilities.modifier(ability)

    def saving_throw_modifier(self, ability: Ability) -> int:
        bonus = self.proficiency_bonus if ability in self.proficiencies.saving_throws else 0
        return self.abilities.modifier(ability) + bonus

    def skill_modifier(self, skill: Skill) -> int:
        ability = SKILL_ABILITY[skill]
        prof = self.proficiencies.skills.get(skill, Proficiency.NONE)
        return self.abilities.modifier(ability) + proficiency_contribution(
            self.proficiency_bonus, prof
        )

    @property
    def passive_perception(self) -> int:
        return 10 + self.skill_modifier(Skill.PERCEPTION)

    @property
    def initiative_modifier(self) -> int:
        return self.abilities.modifier(Ability.DEX)

    @property
    def carried_weight(self) -> float:
        return sum(item.weight * item.quantity for item in self.inventory)

    # --- persistence -------------------------------------------------------

    def to_yaml(self) -> str:
        data = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> CharacterSheet:
        return cls.model_validate(yaml.safe_load(text))

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> CharacterSheet:
        return cls.from_yaml(Path(path).read_text(encoding="utf-8"))
