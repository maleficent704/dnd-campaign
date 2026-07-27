"""P0.4: character sheet schema, derived values, and YAML round-trip."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dndc.rules.checks import Proficiency
from dndc.schema.sheet import (
    SKILL_ABILITY,
    Ability,
    AbilityScores,
    CharacterSheet,
    HitPoints,
    InventoryItem,
    Proficiencies,
    Skill,
    SpellSlotLevel,
)


def sample_sheet(**overrides) -> CharacterSheet:
    data = {
        "name": "Bramble Tealeaf",
        "player": "Sam",
        "species": "Halfling",
        "character_class": "Rogue",
        "level": 1,
        "background": "Urchin",
        "abilities": {"str": 8, "dex": 17, "con": 14, "int": 12, "wis": 13, "cha": 10},
        "proficiencies": {
            "saving_throws": ["dex", "int"],
            "skills": {"stealth": "expertise", "acrobatics": "proficient", "arcana": "none"},
            "armor": ["light"],
            "weapons": ["simple", "shortsword"],
            "languages": ["Common", "Halfling"],
        },
        "hit_points": {"maximum": 10, "current": 10},
        "armor_class": 14,
        "speed": 25,
        "hit_dice": "1d8",
        "inventory": [
            {"name": "Shortsword", "weight": 2.0, "equipped": True},
            {"name": "Rations", "quantity": 5, "weight": 2.0},
        ],
    }
    data.update(overrides)
    return CharacterSheet.model_validate(data)


# --- schema integrity ------------------------------------------------------


def test_every_skill_has_a_governing_ability():
    assert set(SKILL_ABILITY) == set(Skill)


def test_sheet_validates():
    sheet = sample_sheet()
    assert sheet.name == "Bramble Tealeaf"
    assert sheet.level == 1


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        sample_sheet(favourite_colour="green")


def test_current_hp_cannot_exceed_maximum():
    with pytest.raises(ValidationError):
        HitPoints(maximum=10, current=11)


def test_temporary_hp_may_exceed_maximum():
    """Temp HP sits on top of the pool and is not bounded by it."""
    hp = HitPoints(maximum=10, current=10, temporary=15)
    assert hp.temporary == 15


def test_expended_slots_cannot_exceed_total():
    with pytest.raises(ValidationError):
        SpellSlotLevel(total=2, expended=3)


def test_slot_availability():
    assert SpellSlotLevel(total=4, expended=1).available == 3


def test_spell_slot_level_must_be_1_to_9():
    with pytest.raises(ValidationError):
        sample_sheet(spell_slots={0: {"total": 1}})
    with pytest.raises(ValidationError):
        sample_sheet(spell_slots={10: {"total": 1}})


def test_duplicate_saving_throw_rejected():
    with pytest.raises(ValidationError):
        Proficiencies(saving_throws=[Ability.DEX, Ability.DEX])


def test_ability_score_range_enforced():
    with pytest.raises(ValidationError):
        AbilityScores.model_validate({"str": 0, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
    with pytest.raises(ValidationError):
        AbilityScores.model_validate({"str": 31, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})


# --- derived values --------------------------------------------------------


def test_ability_modifiers():
    sheet = sample_sheet()
    assert sheet.ability_modifier(Ability.STR) == -1   # 8
    assert sheet.ability_modifier(Ability.DEX) == 3    # 17
    assert sheet.ability_modifier(Ability.CON) == 2    # 14


def test_proficiency_bonus_tracks_level():
    assert sample_sheet().proficiency_bonus == 2
    assert sample_sheet(level=5).proficiency_bonus == 3


def test_saving_throw_modifier_adds_proficiency_only_where_proficient():
    sheet = sample_sheet()
    assert sheet.saving_throw_modifier(Ability.DEX) == 3 + 2   # proficient
    assert sheet.saving_throw_modifier(Ability.STR) == -1      # not proficient


def test_skill_modifier_respects_expertise_and_absence():
    sheet = sample_sheet()
    assert sheet.skill_modifier(Skill.STEALTH) == 3 + (2 * 2)      # Dex + expertise
    assert sheet.skill_modifier(Skill.ACROBATICS) == 3 + 2         # Dex + proficient
    assert sheet.skill_modifier(Skill.ARCANA) == 1                 # Int, explicitly none
    assert sheet.skill_modifier(Skill.ATHLETICS) == -1             # Str, unlisted


def test_passive_perception():
    sheet = sample_sheet()
    # Wis 13 -> +1, no Perception proficiency
    assert sheet.passive_perception == 11


def test_initiative_is_dex_modifier():
    assert sample_sheet().initiative_modifier == 3


def test_carried_weight_multiplies_by_quantity():
    # 1 shortsword @ 2.0 + 5 rations @ 2.0 = 12.0
    assert sample_sheet().carried_weight == pytest.approx(12.0)


# --- round trip ------------------------------------------------------------


def test_yaml_round_trip_preserves_the_sheet():
    original = sample_sheet(
        spell_slots={1: {"total": 2, "expended": 1}},
        spells_known=["Mage Hand"],
        backstory="Grew up picking pockets in the harbour district.",
    )
    restored = CharacterSheet.from_yaml(original.to_yaml())
    assert restored == original


def test_yaml_round_trip_via_file(tmp_path):
    original = sample_sheet()
    path = tmp_path / "bramble.yaml"
    original.save(path)
    assert CharacterSheet.load(path) == original


def test_yaml_is_human_editable():
    """Sheets are re-editable data (D-005) — the emitted YAML must be plain."""
    text = sample_sheet().to_yaml()
    assert "!!python" not in text
    assert "name: Bramble Tealeaf" in text
    assert "dex: 17" in text


def test_round_trip_preserves_skill_proficiency_levels():
    restored = CharacterSheet.from_yaml(sample_sheet().to_yaml())
    assert restored.proficiencies.skills[Skill.STEALTH] is Proficiency.EXPERTISE


def test_inventory_item_requires_a_name():
    with pytest.raises(ValidationError):
        InventoryItem(name="")
