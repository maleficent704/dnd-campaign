"""P1.4: turning a co-creation concept into a validated character.

Everything here is deterministic — no model, no RNG. The point of these tests is that
the engine, not the GM, decides what a legal character is.
"""

from __future__ import annotations

import pytest

from dndc.rules.allocate import STANDARD_ARRAY
from dndc.rules.build import (
    POINT_BUY_METHOD,
    POINT_BUY_SHAPES,
    BuildError,
    Concept,
    allocate_by_priority,
    build_character,
    class_skill_options,
)
from dndc.rules.allocate import point_buy_total
from dndc.schema.sheet import Ability, Skill
from dndc.srd.repository import SRDRepository

PRIORITY = (Ability.STR, Ability.CON, Ability.DEX, Ability.WIS, Ability.CHA, Ability.INT)


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


def concept(**overrides) -> Concept:
    base = dict(
        name="Brannoc Thorn",
        player="Kelly",
        species="Human",
        character_class="Fighter",
        priority=PRIORITY,
        skills=(Skill.ATHLETICS, Skill.INTIMIDATION),
    )
    base.update(overrides)
    return Concept(**base)


# --- allocation ------------------------------------------------------------


def test_priority_maps_the_array_highest_to_first():
    scores = allocate_by_priority(PRIORITY)
    assert [scores.score(ability) for ability in PRIORITY] == list(STANDARD_ARRAY)


def test_every_ordering_is_legal_by_construction():
    """The point of ranking over numbers: an illegal spread is unrepresentable."""
    reversed_priority = tuple(reversed(PRIORITY))
    scores = allocate_by_priority(reversed_priority)
    assert sorted(scores.as_dict().values(), reverse=True) == list(STANDARD_ARRAY)


def test_a_partial_ranking_is_rejected():
    with pytest.raises(BuildError, match="all six abilities"):
        allocate_by_priority((Ability.STR, Ability.DEX))


def test_a_repeated_ability_is_rejected():
    with pytest.raises(BuildError, match="all six abilities"):
        allocate_by_priority((Ability.STR,) * 6)


@pytest.mark.parametrize("shape", sorted(POINT_BUY_SHAPES))
def test_every_point_buy_shape_costs_exactly_the_budget(shape):
    """A shape table nobody checks is a table that eventually drifts off-budget."""
    scores = allocate_by_priority(PRIORITY, method=POINT_BUY_METHOD, shape=shape)
    assert point_buy_total(scores.as_dict()) == 27


def test_unknown_point_buy_shape_is_rejected():
    with pytest.raises(BuildError, match="unknown point-buy shape"):
        allocate_by_priority(PRIORITY, method=POINT_BUY_METHOD, shape="heroic")


def test_unknown_method_is_rejected():
    with pytest.raises(BuildError, match="unknown allocation method"):
        allocate_by_priority(PRIORITY, method="4d6-drop-lowest")


# --- building --------------------------------------------------------------


def test_builds_a_valid_level_one_character(repo):
    sheet = build_character(concept(), repo)
    assert sheet.name == "Brannoc Thorn"
    assert sheet.level == 1
    assert sheet.species == "Human" and sheet.character_class == "Fighter"
    assert sheet.hit_dice == "1d10"


def test_species_bonuses_apply_after_allocation(repo):
    """Human is +1 to everything, so 15 becomes a 16 — legal only post-allocation."""
    sheet = build_character(concept(), repo)
    assert sheet.abilities.score(Ability.STR) == 16
    assert sheet.abilities.score(Ability.INT) == 9  # the 8, plus one


def test_hit_points_are_hit_die_plus_constitution(repo):
    sheet = build_character(concept(), repo)
    # Fighter d10, CON 14+1=15 -> +2
    assert sheet.hit_points.maximum == 12
    assert sheet.hit_points.current == sheet.hit_points.maximum


def test_saving_throws_come_from_the_class(repo):
    sheet = build_character(concept(), repo)
    assert set(sheet.proficiencies.saving_throws) == {Ability.STR, Ability.CON}


def test_armor_class_uses_the_armor_profile_and_shield(repo):
    sheet = build_character(concept(armor="chain mail", shield=True), repo)
    assert sheet.armor_class == 18  # heavy armour ignores DEX; shield is +2
    assert [item.name for item in sheet.inventory] == ["Chain Mail", "Shield"]


def test_light_armor_adds_dexterity(repo):
    rogueish = concept(
        character_class="Rogue",
        species="Halfling",
        priority=(Ability.DEX, Ability.CON, Ability.WIS, Ability.CHA, Ability.INT, Ability.STR),
        skills=(Skill.STEALTH, Skill.PERCEPTION, Skill.ACROBATICS, Skill.DECEPTION),
        armor="leather armor",
    )
    sheet = build_character(rogueish, repo)
    # DEX 15 + 2 halfling = 17 -> +3, on leather's base 11
    assert sheet.armor_class == 14


def test_medium_armor_caps_the_dexterity_bonus(repo):
    sheet = build_character(
        concept(
            character_class="Rogue",
            priority=(Ability.DEX, Ability.CON, Ability.WIS, Ability.CHA, Ability.INT, Ability.STR),
            skills=(Skill.STEALTH, Skill.PERCEPTION, Skill.ACROBATICS, Skill.DECEPTION),
            armor="scale mail",
        ),
        repo,
    )
    assert sheet.armor_class == 16  # base 14 + min(dex, 2)


def test_unarmored_is_ten_plus_dexterity(repo):
    sheet = build_character(concept(), repo)
    assert sheet.armor_class == 10 + sheet.abilities.modifier(Ability.DEX)


def test_speed_and_languages_come_from_the_species(repo):
    sheet = build_character(concept(species="Halfling", armor=None), repo)
    assert sheet.speed == 25
    assert "Halfling" in sheet.proficiencies.languages


# --- what the engine refuses -----------------------------------------------


def test_a_skill_the_class_cannot_take_is_rejected(repo):
    with pytest.raises(BuildError, match="cannot take arcana"):
        build_character(concept(skills=(Skill.ARCANA, Skill.ATHLETICS)), repo)


def test_the_wrong_number_of_skills_is_rejected(repo):
    with pytest.raises(BuildError, match="chooses exactly 2 skills"):
        build_character(concept(skills=(Skill.ATHLETICS,)), repo)


def test_a_duplicated_skill_is_rejected(repo):
    with pytest.raises(BuildError, match="chosen twice"):
        build_character(concept(skills=(Skill.ATHLETICS, Skill.ATHLETICS)), repo)


def test_an_unknown_species_is_rejected(repo):
    with pytest.raises(BuildError, match="no SRD species"):
        build_character(concept(species="Aarakocra"), repo)


def test_an_unknown_class_is_rejected(repo):
    with pytest.raises(BuildError, match="no SRD class"):
        build_character(concept(character_class="Artificer"), repo)


def test_non_armor_in_the_armor_slot_is_rejected(repo):
    with pytest.raises(BuildError, match="not armor"):
        build_character(concept(armor="longsword"), repo)


# --- spellcasters ----------------------------------------------------------


def wizardly(**overrides) -> Concept:
    base = dict(
        name="Ilsa Vane",
        character_class="Wizard",
        priority=(Ability.INT, Ability.CON, Ability.DEX, Ability.WIS, Ability.CHA, Ability.STR),
        skills=(Skill.ARCANA, Skill.INVESTIGATION),
    )
    base.update(overrides)
    return concept(**base)


def test_a_caster_gets_its_level_one_slots(repo):
    sheet = build_character(wizardly(), repo)
    assert sheet.spell_slots[1].total == 2
    assert sheet.spell_slots[1].available == 2


def test_spells_are_validated_against_the_class_list(repo):
    sheet = build_character(wizardly(spells=("magic missile", "mage hand")), repo)
    assert sheet.spells_known == ["Magic Missile", "Mage Hand"]


def test_a_spell_off_the_class_list_is_rejected(repo):
    with pytest.raises(BuildError, match="not on the Wizard spell list"):
        build_character(wizardly(spells=("cure wounds",)), repo)


def test_a_spell_above_level_one_is_rejected(repo):
    with pytest.raises(BuildError, match="out of reach at level 1"):
        build_character(wizardly(spells=("fireball",)), repo)


def test_a_non_caster_cannot_take_spells(repo):
    with pytest.raises(BuildError, match="does not cast spells"):
        build_character(concept(spells=("magic missile",)), repo)


def test_an_unknown_spell_is_rejected(repo):
    with pytest.raises(BuildError, match="no SRD spell"):
        build_character(wizardly(spells=("eldritch pizza",)), repo)


# --- skill options ---------------------------------------------------------


def test_class_skill_options_read_the_srd_not_a_hand_kept_table(repo):
    allowed, choose = class_skill_options(repo.character_class("rogue"))
    assert choose == 4
    assert Skill.STEALTH in allowed and Skill.ARCANA not in allowed
