"""Typed SRD reference data (P0.2).

These are the *normalized* engine-facing models, not a mirror of the upstream JSON.
Upstream nests every cross-reference as `{index, name, url}` and carries API routing
detail we have no use for; ingestion flattens that to plain index strings and drops the
URLs, so nothing in the engine depends on the shape of somebody else's REST API.

Everything here is reference data: immutable, campaign-independent, and never written
back. Campaign state lives elsewhere. Monsters reuse `AbilityScores` from the character
sheet, so `ability_modifier` and the check/save helpers work identically on a PC and on
a stat block — the rules engine should not care which side of the screen a creature is on.

Edition is SRD 5.1 / 2014 rules; see `data/srd/ATTRIBUTION.md`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from dndc.schema.sheet import Ability, AbilityScores

MAX_SPELL_LEVEL = 9


class _SRDModel(BaseModel):
    """Reference data is frozen — nothing in the engine may mutate the ruleset."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Size(str, Enum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


# --- species ---------------------------------------------------------------


class Subspecies(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    species: str = Field(min_length=1)
    description: str = ""
    ability_bonuses: dict[Ability, int] = Field(default_factory=dict)
    traits: tuple[str, ...] = ()


class Species(_SRDModel):
    """A player species (upstream calls these "races")."""

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    speed: int = Field(ge=0)
    size: Size
    ability_bonuses: dict[Ability, int] = Field(default_factory=dict)
    languages: tuple[str, ...] = ()
    traits: tuple[str, ...] = ()
    subspecies: tuple[str, ...] = ()
    # Flavour text — the GM uses this during co-creation (D-005); the engine does not.
    age: str = ""
    alignment: str = ""
    size_description: str = ""
    language_description: str = ""


# --- classes ---------------------------------------------------------------


class ProficiencyChoice(_SRDModel):
    """"Choose N from ..." — the co-creation flow presents these to the player."""

    description: str = ""
    choose: int = Field(ge=1)
    options: tuple[str, ...] = ()


class ClassLevel(_SRDModel):
    level: int = Field(ge=1, le=20)
    proficiency_bonus: int = Field(ge=2, le=6)
    features: tuple[str, ...] = ()
    ability_score_bonuses: int = Field(default=0, ge=0)
    #: Spell slots by spell level, e.g. {1: 4, 2: 2}. Empty for non-casters.
    spell_slots: dict[int, int] = Field(default_factory=dict)
    cantrips_known: int | None = None
    spells_known: int | None = None
    #: Class-unique counters (rage_count, sneak_attack_dice, ...). Shape varies by class.
    class_specific: dict[str, object] = Field(default_factory=dict)


class CharacterClass(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    hit_die: int = Field(ge=4, le=12)
    saving_throws: tuple[Ability, ...] = ()
    proficiencies: tuple[str, ...] = ()
    proficiency_choices: tuple[ProficiencyChoice, ...] = ()
    starting_equipment: tuple[str, ...] = ()
    spellcasting_ability: Ability | None = None
    subclasses: tuple[str, ...] = ()
    #: Keyed by level. Ingest trims this to the configured scope (default L1-5).
    levels: dict[int, ClassLevel] = Field(default_factory=dict)


# --- spells ----------------------------------------------------------------


class SpellDamage(_SRDModel):
    damage_type: str | None = None
    #: Damage by the slot level the spell is cast at, e.g. {2: "4d4", 3: "5d4"}.
    at_slot_level: dict[int, str] = Field(default_factory=dict)
    #: Cantrip scaling, keyed by character level.
    at_character_level: dict[int, str] = Field(default_factory=dict)


class AreaOfEffect(_SRDModel):
    type: str
    size: int = Field(ge=0)


class Spell(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    level: int = Field(ge=0, le=MAX_SPELL_LEVEL)  # 0 == cantrip
    school: str = ""
    casting_time: str = ""
    range: str = ""
    duration: str = ""
    components: tuple[str, ...] = ()
    material: str | None = None
    ritual: bool = False
    concentration: bool = False
    description: tuple[str, ...] = ()
    higher_level: tuple[str, ...] = ()
    classes: tuple[str, ...] = ()
    subclasses: tuple[str, ...] = ()
    attack_type: str | None = None
    #: Saving throw ability, when the spell calls for one.
    save_ability: Ability | None = None
    damage: SpellDamage | None = None
    area_of_effect: AreaOfEffect | None = None
    heal_at_slot_level: dict[int, str] = Field(default_factory=dict)
    #: Upstream writes healing/Spiritual Weapon amounts as "1d8 + MOD", where MOD is the
    #: caster's spellcasting ability modifier. That is not a rollable expression, so
    #: ingestion strips it to "1d8" and raises this flag instead — the caller adds the
    #: modifier from the character sheet. Keeps prose out of the dice engine (D-001).
    adds_spellcasting_modifier: bool = False

    @property
    def is_cantrip(self) -> bool:
        return self.level == 0


# --- monsters --------------------------------------------------------------


class MonsterDamage(_SRDModel):
    damage_dice: str = ""
    damage_type: str | None = None


class MonsterAction(_SRDModel):
    name: str = Field(min_length=1)
    description: str = ""
    attack_bonus: int | None = None
    damage: tuple[MonsterDamage, ...] = ()
    #: Present on multiattack-style actions and recharge abilities.
    usage: dict[str, object] = Field(default_factory=dict)
    dc_ability: Ability | None = None
    dc_value: int | None = None


class Monster(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    size: Size
    type: str = ""
    subtype: str | None = None
    alignment: str = ""
    #: Resolved to a single usable number; `armor_class_kind` keeps the provenance
    #: (natural / dex / armor / spell / condition) for narration.
    armor_class: int = Field(ge=0)
    armor_class_kind: str = ""
    hit_points: int = Field(ge=1)
    hit_dice: str = ""
    #: Movement in feet by mode: {"walk": 30, "fly": 60}. `hover` is a flag upstream.
    speed: dict[str, int] = Field(default_factory=dict)
    can_hover: bool = False
    abilities: AbilityScores
    challenge_rating: float = Field(ge=0)
    proficiency_bonus: int = Field(ge=2)
    xp: int = Field(ge=0)
    #: Proficiency index -> total modifier, e.g. {"skill-stealth": 6}.
    proficiencies: dict[str, int] = Field(default_factory=dict)
    damage_vulnerabilities: tuple[str, ...] = ()
    damage_resistances: tuple[str, ...] = ()
    damage_immunities: tuple[str, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    senses: dict[str, str] = Field(default_factory=dict)
    passive_perception: int = Field(ge=0)
    languages: str = ""
    description: str = ""
    special_abilities: tuple[MonsterAction, ...] = ()
    actions: tuple[MonsterAction, ...] = ()
    legendary_actions: tuple[MonsterAction, ...] = ()
    reactions: tuple[MonsterAction, ...] = ()


# --- equipment -------------------------------------------------------------


class Cost(_SRDModel):
    quantity: int = Field(ge=0)
    unit: str = ""

    @property
    def in_copper(self) -> int:
        """Normalized to copper so prices are comparable across units."""
        return self.quantity * {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}.get(
            self.unit, 0
        )


class WeaponProfile(_SRDModel):
    category: str = ""
    weapon_range: str = ""
    damage_dice: str = ""
    damage_type: str | None = None
    two_handed_damage_dice: str | None = None
    properties: tuple[str, ...] = ()
    range_normal: int | None = None
    range_long: int | None = None
    throw_range_normal: int | None = None
    throw_range_long: int | None = None


class ArmorProfile(_SRDModel):
    category: str = ""
    base_ac: int = Field(ge=0)
    dex_bonus: bool = False
    max_dex_bonus: int | None = None
    strength_minimum: int = Field(default=0, ge=0)
    stealth_disadvantage: bool = False


class Equipment(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = ""
    cost: Cost
    weight: float = Field(default=0.0, ge=0)
    description: tuple[str, ...] = ()
    weapon: WeaponProfile | None = None
    armor: ArmorProfile | None = None


# --- conditions ------------------------------------------------------------


class Condition(_SRDModel):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: tuple[str, ...] = ()


# --- the dataset -----------------------------------------------------------


class IngestScope(_SRDModel):
    """How much of the SRD to normalize.

    Defaults match the P0.2 scope note (a starting campaign). Widening is a
    parameter change, not a rewrite — Phase 3 will want a higher CR ceiling.
    """

    max_class_level: int = Field(default=5, ge=1, le=20)
    max_challenge_rating: float = Field(default=5.0, ge=0)


class SRDData(_SRDModel):
    """The whole normalized ruleset, every collection keyed by SRD index."""

    scope: IngestScope = IngestScope()
    species: dict[str, Species] = Field(default_factory=dict)
    subspecies: dict[str, Subspecies] = Field(default_factory=dict)
    classes: dict[str, CharacterClass] = Field(default_factory=dict)
    spells: dict[str, Spell] = Field(default_factory=dict)
    monsters: dict[str, Monster] = Field(default_factory=dict)
    equipment: dict[str, Equipment] = Field(default_factory=dict)
    conditions: dict[str, Condition] = Field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "species": len(self.species),
            "subspecies": len(self.subspecies),
            "classes": len(self.classes),
            "spells": len(self.spells),
            "monsters": len(self.monsters),
            "equipment": len(self.equipment),
            "conditions": len(self.conditions),
        }

    def monsters_by_cr(self, minimum: float, maximum: float) -> list[Monster]:
        """Encounter building (Phase 3) selects on CR; sorted for deterministic output."""
        return sorted(
            (m for m in self.monsters.values() if minimum <= m.challenge_rating <= maximum),
            key=lambda m: (m.challenge_rating, m.index),
        )

    def spells_for_class(self, class_index: str, max_level: int = MAX_SPELL_LEVEL) -> list[Spell]:
        return sorted(
            (
                s
                for s in self.spells.values()
                if class_index in s.classes and s.level <= max_level
            ),
            key=lambda s: (s.level, s.index),
        )
