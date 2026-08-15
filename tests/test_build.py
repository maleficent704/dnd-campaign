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
    grant_issues,
)
from dndc.rules.allocate import point_buy_total
from dndc.rules.checks import Proficiency
from dndc.schema.sheet import AbilityScores, Ability, Proficiencies, Skill
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
        # Human grants one language of choice; the engine now insists it be made.
        languages=("dwarvish",),
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
        expertise=("stealth", "perception"),
        languages=(),  # Halfling grants no choice
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
            expertise=("stealth", "perception"),
            armor="scale mail",
        ),
        repo,
    )
    assert sheet.armor_class == 16  # base 14 + min(dex, 2)


def test_unarmored_is_ten_plus_dexterity(repo):
    sheet = build_character(concept(), repo)
    assert sheet.armor_class == 10 + sheet.abilities.modifier(Ability.DEX)


def test_speed_and_languages_come_from_the_species(repo):
    sheet = build_character(concept(species="Halfling", armor=None, languages=()), repo)
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


# --- choice-points inside grants (playtest bug review, 2026-08-05) ----------
#
# Fable's review of the first co-created character found four omissions, all the same
# shape: a grant with a choice inside it was silently dropped. These pin each one, plus
# a sweep asserting no species/class combination can produce a sheet that quietly
# ignores a required choice.


def half_elf_rogue(**overrides) -> Concept:
    base = dict(
        name="Corin Vale",
        species="Half-Elf",
        character_class="Rogue",
        priority=(Ability.CHA, Ability.DEX, Ability.CON, Ability.WIS, Ability.INT, Ability.STR),
        skills=(Skill.DECEPTION, Skill.PERSUASION, Skill.STEALTH, Skill.INSIGHT),
        ability_bonus_picks=(Ability.DEX, Ability.CON),
        expertise=("deception", "thieves' tools"),
        languages=("dwarvish",),
    )
    base.update(overrides)
    return concept(**base)


def test_floating_species_bonuses_are_applied(repo):
    """Bug 1: the Half-Elf's +2 Cha landed, the two floating +1s vanished."""
    sheet = build_character(half_elf_rogue(), repo)
    assert sheet.abilities.score(Ability.CHA) == 17  # 15 + fixed 2
    assert sheet.abilities.score(Ability.DEX) == 15  # 14 + chosen 1
    assert sheet.abilities.score(Ability.CON) == 14  # 13 + chosen 1


def test_a_species_with_floating_bonuses_demands_them(repo):
    with pytest.raises(BuildError, match="2 abilities of your choice"):
        build_character(half_elf_rogue(ability_bonus_picks=()), repo)


def test_the_wrong_number_of_floating_bonuses_is_rejected(repo):
    with pytest.raises(BuildError, match="pick exactly 2"):
        build_character(half_elf_rogue(ability_bonus_picks=(Ability.DEX,)), repo)


def test_floating_bonuses_cannot_repeat_one_ability(repo):
    with pytest.raises(BuildError, match="picked twice"):
        build_character(half_elf_rogue(ability_bonus_picks=(Ability.DEX, Ability.DEX)), repo)


def test_a_species_without_the_choice_refuses_picks(repo):
    with pytest.raises(BuildError, match="no ability bonuses to choose"):
        build_character(concept(ability_bonus_picks=(Ability.STR,)), repo)


def test_thieves_tools_proficiency_comes_through(repo):
    """Bug 2: dropped because the old keyword filter had no word for it."""
    sheet = build_character(half_elf_rogue(), repo)
    assert "Thieves Tools" in sheet.proficiencies.tools


def test_class_proficiencies_are_sorted_by_srd_category(repo):
    sheet = build_character(half_elf_rogue(), repo)
    assert sheet.proficiencies.armor == ["Light Armor"]
    assert "Rapiers" in sheet.proficiencies.weapons
    # Saving throws and skills have their own fields; they must not appear twice.
    assert not any("Saving" in p for p in sheet.proficiencies.weapons)
    assert not any("Skill" in p for p in sheet.proficiencies.tools)


def test_expertise_is_applied_and_doubles_the_bonus(repo):
    """Bug 3: all four skills came out `proficient`."""
    sheet = build_character(half_elf_rogue(), repo)
    assert sheet.proficiencies.skills[Skill.DECEPTION] is Proficiency.EXPERTISE
    assert sheet.proficiencies.skills[Skill.STEALTH] is Proficiency.PROFICIENT
    # Cha 17 (+3) with PB 2 doubled.
    assert sheet.skill_modifier(Skill.DECEPTION) == 7


def test_a_class_with_expertise_demands_it(repo):
    with pytest.raises(BuildError, match="expertise in exactly 2"):
        build_character(half_elf_rogue(expertise=()), repo)


def test_expertise_must_be_something_the_character_is_proficient_in(repo):
    with pytest.raises(BuildError, match="must be something this character is proficient"):
        build_character(half_elf_rogue(expertise=("athletics", "stealth")), repo)


def test_a_class_without_expertise_refuses_it(repo):
    with pytest.raises(BuildError, match="no expertise at level 1"):
        build_character(concept(expertise=("athletics",)), repo)


def test_the_chosen_extra_language_is_added(repo):
    """Bug 4: Half-Elf's bonus language never appeared."""
    sheet = build_character(half_elf_rogue(), repo)
    assert sheet.proficiencies.languages == ["Common", "Elvish", "Dwarvish"]


def test_a_species_with_a_language_choice_demands_it(repo):
    with pytest.raises(BuildError, match="1 extra language"):
        build_character(half_elf_rogue(languages=()), repo)


def test_the_extra_language_cannot_be_one_already_known(repo):
    with pytest.raises(BuildError, match="already known"):
        build_character(half_elf_rogue(languages=("elvish",)), repo)


def test_an_invented_language_is_rejected(repo):
    with pytest.raises(BuildError, match="not an SRD language"):
        build_character(half_elf_rogue(languages=("thieves cant",)), repo)


def test_a_species_without_a_language_choice_refuses_one(repo):
    # Elf, not Human — Human is one of the two species that *does* grant a choice.
    with pytest.raises(BuildError, match="no extra language"):
        build_character(concept(species="Elf", languages=("dwarvish",)), repo)


# --- the sweep -------------------------------------------------------------


@pytest.mark.parametrize("species_name", ["Human", "Half-Elf", "Dwarf", "Elf", "Halfling"])
@pytest.mark.parametrize("class_name", ["Fighter", "Rogue", "Wizard", "Cleric"])
def test_no_combination_can_silently_skip_a_required_choice(repo, species_name, class_name):
    """The general form of all four bugs: if the SRD demands a choice and the concept
    does not carry it, the build must fail rather than emit a short sheet."""
    species = repo.species(species_name)
    character_class = repo.character_class(class_name)
    allowed, choose = class_skill_options(character_class)

    # Built directly rather than through `concept()`, whose defaults already answer some
    # of the choices — the point here is a concept that answers none of them.
    bare = Concept(
        name="Nobody",
        player="Kelly",
        species=species_name,
        character_class=class_name,
        priority=PRIORITY,
        skills=tuple(sorted(allowed, key=lambda s: s.value)[:choose]),
    )
    demands_a_choice = (
        species.ability_bonus_options is not None
        or species.language_options is not None
        or (character_class.levels.get(1) and character_class.levels[1].expertise_choices)
    )

    if demands_a_choice:
        with pytest.raises(BuildError):
            build_character(bare, repo)
    else:
        sheet = build_character(bare, repo)
        # Fixed grants still have to be complete.
        assert set(sheet.proficiencies.saving_throws) == set(character_class.saving_throws)
        assert sheet.speed == species.speed
        assert len(sheet.proficiencies.languages) == len(species.languages)


# --- the grant validator ---------------------------------------------------


def test_a_built_sheet_has_no_grant_issues(repo):
    assert grant_issues(build_character(half_elf_rogue(), repo), repo) == []


def test_the_validator_catches_all_four_original_bugs(repo):
    """A sheet in the shape the first co-created character came out in."""
    sheet = build_character(half_elf_rogue(), repo)
    short = sheet.model_copy(update={
        "abilities": AbilityScores(str=8, dex=14, con=13, int=10, wis=12, cha=17),
        "proficiencies": Proficiencies(
            saving_throws=list(sheet.proficiencies.saving_throws),
            skills={skill: Proficiency.PROFICIENT for skill in sheet.proficiencies.skills},
            armor=sheet.proficiencies.armor,
            weapons=sheet.proficiencies.weapons,
            tools=[],
            languages=["Common", "Elvish"],
        ),
    })
    issues = " | ".join(grant_issues(short, repo))
    assert "abilities of your choice" in issues   # floating +1s
    assert "expertise" in issues                  # rogue expertise
    assert "language" in issues                   # bonus language
    assert "Thieves Tools" in issues              # tools proficiency


def test_the_validator_tolerates_a_hand_written_apostrophe(repo):
    """Sheets are re-editable data (D-005); a human writes "Thieves' Tools"."""
    sheet = build_character(half_elf_rogue(), repo)
    edited = sheet.model_copy(update={
        "proficiencies": Proficiencies(
            **{
                **sheet.proficiencies.model_dump(),
                # Re-parsed, not copied: this is the path a hand-edited YAML takes.
                "tools": {"Thieves' Tools": Proficiency.EXPERTISE},
            }
        )
    })
    assert grant_issues(edited, repo) == []


def test_the_validator_reports_an_unknown_species(repo):
    sheet = build_character(concept(), repo)
    (issue,) = grant_issues(sheet.model_copy(update={"species": "Aarakocra"}), repo)
    assert "no SRD species" in issue


# --- backgrounds and starting kit (ingest task, 2026-08-15) ----------------


def test_a_background_grants_its_skills_on_top_of_the_class_picks(repo):
    """The 2026-08-05 finding: `background` was a string that granted nothing."""
    sheet = build_character(
        concept(character_class="Fighter", skills=(Skill.ATHLETICS, Skill.PERCEPTION),
                background="Acolyte"),
        repo,
    )
    assert sheet.proficiencies.skills[Skill.INSIGHT] is Proficiency.PROFICIENT
    assert sheet.proficiencies.skills[Skill.RELIGION] is Proficiency.PROFICIENT
    assert sheet.proficiencies.skills[Skill.ATHLETICS] is Proficiency.PROFICIENT


def test_a_class_pick_that_duplicates_a_background_grant_is_refused(repo):
    """5e's answer is to choose something else, so the engine says so — to the GM, which
    is where engine objections go (D-005), not to the player."""
    with pytest.raises(BuildError) as caught:
        build_character(
            concept(character_class="Fighter", skills=(Skill.INSIGHT, Skill.ATHLETICS),
                    background="Acolyte"),
            repo,
        )
    assert "Acolyte already grants insight" in str(caught.value)


def test_a_background_the_srd_never_heard_of_is_still_flavour(repo):
    """The SRD has one background. Every character the table has made so far has an
    invented one, and refusing to build them would be the ruleset overruling the fiction
    about something with no mechanical stake."""
    sheet = build_character(concept(background="Urchin"), repo)
    assert sheet.background == "Urchin"


def test_a_background_brings_its_starting_kit(repo):
    sheet = build_character(concept(background="Acolyte"), repo)
    carried = {item.name: item.quantity for item in sheet.inventory}
    assert carried.get("Clothes, common") == 1
    assert carried.get("Pouch") == 1


def test_starting_equipment_carries_the_weight_the_srd_gives_it(repo):
    """`carried_weight` was a number that looked authoritative and was not — everything
    but armor weighed zero."""
    sheet = build_character(concept(equipment=("rope-hempen-50-feet",)), repo)
    rope = next(item for item in sheet.inventory if "rope" in item.name.lower())
    assert rope.weight > 0


def test_an_item_the_srd_does_not_know_is_kept_and_weighs_nothing(repo):
    """A keepsake is not equipment. Losing it because the ruleset has no entry would be
    the sheet contradicting the fiction — the failure P2.4 exists to end."""
    sheet = build_character(concept(equipment=("grandmother's locket",)), repo)
    locket = next(item for item in sheet.inventory if "locket" in item.name)
    assert locket.weight == 0.0


def test_a_sheet_missing_its_background_skills_is_flagged(repo):
    """The hand-edited case — and every character built before backgrounds granted
    anything at all."""
    sheet = build_character(concept(background="Urchin"), repo)
    sheet.background = "Acolyte"

    issues = grant_issues(sheet, repo)
    assert any("Acolyte grants insight, religion" in issue for issue in issues)


def test_an_invented_background_is_not_an_issue(repo):
    """The table invents most of them. Flagging every character for having a background
    would train the reader to ignore this list."""
    sheet = build_character(concept(background="Urchin"), repo)
    assert grant_issues(sheet, repo) == []
