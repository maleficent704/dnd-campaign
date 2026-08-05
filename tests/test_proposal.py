"""P1.4: parsing the GM's `[[PROPOSE: ...]]` and `[[FACT: ...]]` tags.

Same contract as the check-request parser: forgiving about surface form, strict about
meaning. The producer is a language model, so the tests below are mostly about the
sloppy-but-unambiguous forms it will actually emit.
"""

from __future__ import annotations

import pytest

from dndc.gm.proposal import ProposalError, find_facts, find_proposal, strip_tags
from dndc.rules.build import POINT_BUY_METHOD, STANDARD_ARRAY_METHOD
from dndc.schema.sheet import Ability, Skill

CANONICAL = """
Here's what I have in mind.

[[PROPOSE:
name: Brannoc Thorn
species: Human
class: Fighter
background: Soldier
priority: str, con, dex, wis, cha, int
skills: athletics, intimidation
armor: chain mail
shield: yes
equipment: longsword, bedroll
]]
"""


def parse(text: str, player: str = "Kelly"):
    proposal = find_proposal(text, player=player)
    assert proposal is not None
    return proposal.concept


def test_parses_the_canonical_form():
    concept = parse(CANONICAL)
    assert concept.name == "Brannoc Thorn"
    assert concept.player == "Kelly"
    assert concept.species == "Human"
    assert concept.character_class == "Fighter"
    assert concept.background == "Soldier"
    assert concept.priority[0] is Ability.STR and concept.priority[-1] is Ability.INT
    assert concept.skills == (Skill.ATHLETICS, Skill.INTIMIDATION)
    assert concept.armor == "chain mail"
    assert concept.shield is True
    assert concept.equipment == ("longsword", "bedroll")
    assert concept.method == STANDARD_ARRAY_METHOD


def test_prose_without_a_tag_is_not_a_proposal():
    assert find_proposal("So — a soldier, then? What did they leave behind?", "Kelly") is None


def test_full_ability_names_and_odd_casing():
    concept = parse(
        "[[Propose:\nName: X\nSpecies: Elf\nClass: Rogue\n"
        "Priority: Dexterity, Charisma, Constitution, Wisdom, Intelligence, Strength\n]]"
    )
    assert concept.priority[0] is Ability.DEX
    assert concept.name == "X"


def test_priority_written_as_a_numbered_list():
    concept = parse(
        "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: 1. dex 2. wis 3. con 4. int 5. cha 6. str\n]]"
    )
    assert concept.priority[:2] == (Ability.DEX, Ability.WIS)


def test_priority_split_across_lines_and_joined_with_and():
    concept = parse(
        "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis\n  int, cha and str\n]]"
    )
    assert len(concept.priority) == 6


def test_key_aliases_the_model_might_reach_for():
    concept = parse(
        "[[PROPOSE:\nname: X\nrace: Dwarf\ncharacter_class: Cleric\n"
        "abilities: wis, con, str, cha, int, dex\ngear: mace\n]]"
    )
    assert concept.species == "Dwarf"
    assert concept.character_class == "Cleric"
    assert concept.equipment == ("mace",)


def test_sleight_of_hand_survives_the_space_to_underscore_mapping():
    concept = parse(
        "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\nskills: sleight of hand, stealth\n]]"
    )
    assert concept.skills == (Skill.SLEIGHT_OF_HAND, Skill.STEALTH)


def test_backstory_keeps_a_colon_and_a_wrapped_second_line():
    """A `key:` the parser doesn't know is prose — otherwise half the sentence vanishes."""
    concept = parse(
        "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\n"
        "backstory: She left Kelmore: a mining town,\nand never wrote home.\n]]"
    )
    assert concept.backstory == "She left Kelmore: a mining town, and never wrote home."


def test_point_buy_is_recognised_however_it_is_spelled():
    concept = parse(
        "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\nmethod: Point Buy\nshape: focused\n]]"
    )
    assert concept.method == POINT_BUY_METHOD
    assert concept.shape == "focused"


@pytest.mark.parametrize("value,expected", [("no", False), ("none", False), ("yes", True)])
def test_shield_flag(value, expected):
    concept = parse(
        f"[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        f"priority: dex, con, wis, int, cha, str\nshield: {value}\n]]"
    )
    assert concept.shield is expected


def test_the_last_proposal_wins_when_the_gm_revises_mid_reply():
    concept = parse(
        "[[PROPOSE:\nname: First\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\n]]\n"
        "Actually, better:\n"
        "[[PROPOSE:\nname: Second\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\n]]"
    )
    assert concept.name == "Second"


# --- what it refuses -------------------------------------------------------


def test_an_incomplete_ability_ranking_raises():
    with pytest.raises(ProposalError, match="rank all six"):
        parse("[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\npriority: dex, con\n]]")


def test_a_duplicated_ability_raises():
    with pytest.raises(ProposalError, match="listed twice"):
        parse(
            "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
            "priority: dex, dex, con, wis, int, cha\n]]"
        )


def test_an_unknown_ability_raises():
    with pytest.raises(ProposalError, match="unknown ability"):
        parse(
            "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
            "priority: dex, con, wis, int, cha, luck\n]]"
        )


def test_an_unknown_skill_raises_rather_than_being_dropped():
    """A silently discarded proficiency is a sheet that is wrong where nobody looks."""
    with pytest.raises(ProposalError, match="unknown skill"):
        parse(
            "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
            "priority: dex, con, wis, int, cha, str\nskills: lockpicking\n]]"
        )


def test_a_missing_required_field_raises():
    with pytest.raises(ProposalError, match="missing: species"):
        parse("[[PROPOSE:\nname: X\nclass: Rogue\npriority: dex, con, wis, int, cha, str\n]]")


def test_an_empty_proposal_raises():
    with pytest.raises(ProposalError, match="empty"):
        parse("[[PROPOSE:\n\n]]")


def test_an_unknown_allocation_method_raises():
    with pytest.raises(ProposalError, match="unknown allocation method"):
        parse(
            "[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
            "priority: dex, con, wis, int, cha, str\nmethod: roll 3d6 down the line\n]]"
        )


# --- facts -----------------------------------------------------------------


def test_facts_are_collected_in_order():
    facts = find_facts(
        "Good. [[FACT: Brannoc owes a debt to the Kelmore garrison.]]\n"
        "And: [[FACT: His brother died at the siege.]]"
    )
    assert facts == [
        "Brannoc owes a debt to the Kelmore garrison.",
        "His brother died at the siege.",
    ]


def test_a_wrapped_fact_is_collapsed_to_one_line():
    (fact,) = find_facts("[[FACT: She left home\n  in the winter.]]")
    assert fact == "She left home in the winter."


def test_no_facts_is_an_empty_list():
    assert find_facts("Tell me about the brother.") == []


# --- stripping -------------------------------------------------------------


def test_tags_are_stripped_from_what_the_player_reads():
    text = strip_tags(CANONICAL)
    assert "Here's what I have in mind." in text
    assert "PROPOSE" not in text and "priority" not in text


def test_fact_tags_are_stripped_too():
    assert strip_tags("Noted. [[FACT: He hates boats.]]") == "Noted."


def test_an_empty_code_fence_left_by_a_stripped_tag_is_cleaned_up():
    """Caught live: the GM wraps the tag in a fence, so removing it left ``` ``` on
    screen — machine residue in front of the players."""
    text = strip_tags(
        "Here she is.\n\n```\n[[PROPOSE:\nname: X\nspecies: Elf\nclass: Rogue\n"
        "priority: dex, con, wis, int, cha, str\n]]\n```\n\nWhat do you think?"
    )
    assert "```" not in text
    assert text == "Here she is.\n\nWhat do you think?"


def test_a_fence_with_real_content_survives():
    assert "```" in strip_tags("A sign:\n\n```\nCLOSED\n```")
