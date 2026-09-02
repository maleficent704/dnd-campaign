"""Original backgrounds: the tag, the shape rules, the book, and the grants.

Fable's 2026-08-15 (c) ruling — co-creation proposes an original background, the engine
validates the shape deterministically, the table confirms, confirmed ones persist as
campaign data. Offline throughout; the GM is a `MockBackend` replaying scripted replies.
"""

from __future__ import annotations

import pytest

from dndc.game import campaign as campaign_module
from dndc.game.campaign import create_campaign
from dndc.game.creation import CreationSession, load_campaign_backgrounds
from dndc.gm.backgroundtag import find_background, strip_background_tags
from dndc.logging import SessionLog, read_log
from dndc.models.mock import MockBackend
from dndc.rules.background import (
    BackgroundError,
    describe_grants,
    validate_background,
)
from dndc.rules.build import BuildError, Concept, build_character, grant_issues
from dndc.schema.campaign import BackgroundBook, CampaignBackground
from dndc.schema.events import EventType
from dndc.schema.sheet import Ability, Proficiency, Skill
from dndc.srd.repository import SRDRepository

GRIFTER = """She has been running the coast road since she was twelve.

[[BACKGROUND:
name: Salt-Road Grifter
skills: deception, sleight of hand
tool: forgery kit
feature: Known Face on the Road
description: You know which inns on the coast road ask questions and which do not.
]]

[[PROPOSE:
name: Corin Vale
species: Human
class: Fighter
background: Salt-Road Grifter
priority: dex, cha, con, wis, int, str
skills: athletics, intimidation
languages: dwarvish
]]"""

PRIORITY = (Ability.DEX, Ability.CHA, Ability.CON, Ability.WIS, Ability.INT, Ability.STR)


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


@pytest.fixture
def campaigns_root(tmp_path, monkeypatch):
    root = tmp_path / "campaigns"
    monkeypatch.setattr(campaign_module, "default_campaigns_root", lambda: root)
    return root


def grifter() -> CampaignBackground:
    return validate_background(
        name="Salt-Road Grifter",
        skills=["deception", "sleight of hand"],
        tool="forgery kit",
        feature="Known Face on the Road",
    )


def concept(**overrides) -> Concept:
    fields = {
        "name": "Corin Vale",
        "player": "Kelly",
        "species": "Human",
        "character_class": "Fighter",
        "priority": PRIORITY,
        "skills": (Skill.ATHLETICS, Skill.INTIMIDATION),
        "background": "Salt-Road Grifter",
        "languages": ("dwarvish",),
    }
    fields.update(overrides)
    return Concept(**fields)


def convo(repo, responses, book=None, confirm=None, log=None) -> CreationSession:
    return CreationSession(
        backend=MockBackend(responses=responses),
        repo=repo,
        player="Kelly",
        log=log,
        backgrounds=book,
        confirm_background=confirm,
    )


# --- the tag ---------------------------------------------------------------


def test_the_tag_parses_into_its_pieces():
    tag = find_background(GRIFTER)
    assert tag is not None
    assert tag.name == "Salt-Road Grifter"
    assert tag.skills == ("deception", "sleight of hand")
    assert tag.tool == "forgery kit"
    assert tag.language is None
    assert tag.feature == "Known Face on the Road"
    assert "coast road" in tag.description


def test_a_description_may_wrap_across_lines():
    """The `[[PROPOSE:]]` rule: an unknown `key:` continues the field it is inside.

    Without it, `description: She left Kelmore: a mining town` loses its second half — or
    worse, half a sentence becomes a field nobody reads.
    """
    tag = find_background(
        "[[BACKGROUND:\n"
        "name: Ledger Clerk\n"
        "skills: history, investigation\n"
        "description: She left Kelmore: a mining town\n"
        "that had stopped mining anything.\n"
        "]]"
    )
    assert tag.description == (
        "She left Kelmore: a mining town that had stopped mining anything."
    )


def test_the_last_tag_in_a_reply_wins():
    """A GM revising inside one reply means the revision."""
    text = (
        "[[BACKGROUND:\nname: First\nskills: history, nature\n]]\n"
        "on reflection —\n"
        "[[BACKGROUND:\nname: Second\nskills: history, nature\n]]"
    )
    assert find_background(text).name == "Second"


def test_no_tag_is_not_an_error():
    assert find_background("Just talking, no proposal yet.") is None


@pytest.mark.parametrize(
    "line",
    ["equipment: a longbow", "gold: 15", "ability: +1 charisma", "expertise: deception"],
)
def test_a_key_naming_something_a_background_cannot_grant_is_refused(line):
    """Refused by name rather than dropped.

    A silently ignored `equipment:` line is the GM telling the player about gear the sheet
    never received — the fiction/state divergence P2.4 exists to end.
    """
    with pytest.raises(BackgroundError):
        find_background(f"[[BACKGROUND:\nname: X\nskills: history, nature\n{line}\n]]")


def test_a_language_of_your_choice_is_refused():
    """The extra is a language the background *teaches* — a choice gets left half-spent."""
    with pytest.raises(BackgroundError, match="name it"):
        find_background(
            "[[BACKGROUND:\nname: X\nskills: history, nature\n"
            "language: one of your choice\n]]"
        )


def test_a_tag_without_skills_is_refused():
    with pytest.raises(BackgroundError, match="skills"):
        find_background("[[BACKGROUND:\nname: Nameless Thing\n]]")


def test_the_tag_never_reaches_the_player():
    stripped = strip_background_tags(GRIFTER)
    assert "BACKGROUND" not in stripped
    assert "coast road since she was twelve" in stripped


# --- the shape rules -------------------------------------------------------


def test_a_well_formed_background_is_granted():
    background = grifter()
    assert background.index == "salt-road-grifter"
    assert background.skills == (Skill.DECEPTION, Skill.SLEIGHT_OF_HAND)
    assert background.tools == ("forgery kit",)
    assert background.languages == ()
    assert describe_grants(background) == "deception, sleight of hand; forgery kit"


@pytest.mark.parametrize(
    "skills",
    [["deception"], ["deception", "stealth", "athletics"], []],
)
def test_a_background_grants_exactly_two_skills(skills):
    with pytest.raises(BackgroundError, match="exactly 2 skills"):
        validate_background(name="X", skills=skills)


def test_the_same_skill_twice_is_not_two_skills():
    with pytest.raises(BackgroundError, match="twice"):
        validate_background(name="X", skills=["stealth", "Stealth"])


def test_an_invented_skill_is_refused():
    with pytest.raises(BackgroundError, match="not a skill"):
        validate_background(name="X", skills=["deception", "haggling"])


def test_the_extra_is_a_tool_or_a_language_never_both():
    with pytest.raises(BackgroundError, match="not both"):
        validate_background(
            name="X",
            skills=["deception", "stealth"],
            tool="forgery kit",
            language="dwarvish",
        )


def test_a_language_must_be_one_this_ruleset_names(repo):
    with pytest.raises(BackgroundError, match="not a language"):
        validate_background(
            name="X",
            skills=["deception", "stealth"],
            language="Aklo",
            languages_known=repo.known_languages(),
        )
    granted = validate_background(
        name="X",
        skills=["deception", "stealth"],
        language="dwarvish",
        languages_known=repo.known_languages(),
    )
    assert granted.languages == ("dwarvish",)


@pytest.mark.parametrize(
    "fields",
    [
        {"feature": "Silver Tongue: +1 to Charisma checks"},
        {"description": "Years of practice give her -2 on nothing at all."},
        {"name": "Veteran +1"},
    ],
)
def test_a_numeric_bonus_anywhere_in_the_prose_is_refused(fields):
    """D-001's line. There is nowhere in the type to put a bonus, so prose is the only
    way one could arrive — and a bonus the engine never granted is one the GM would then
    narrate as real."""
    payload = {"name": "X", "skills": ["deception", "stealth"], **fields}
    with pytest.raises(BackgroundError, match="numeric bonus"):
        validate_background(**payload)


def test_the_rulesets_own_background_may_not_be_overwritten(repo):
    """Acolyte is the one SRD row and stays the one SRD row."""
    with pytest.raises(BackgroundError, match="already has a background called Acolyte"):
        validate_background(
            name="acolyte",
            skills=["deception", "stealth"],
            srd_names=[b.name for b in repo.data.backgrounds.values()],
        )


def test_a_name_that_is_a_sentence_is_refused():
    with pytest.raises(BackgroundError, match="not a sentence"):
        validate_background(
            name="A woman who grew up running errands for smugglers on the coast road",
            skills=["deception", "stealth"],
        )


def test_redeclaring_an_existing_background_returns_the_stored_one():
    """The GM naming what the campaign already carries is reuse, not a clash — and the
    stored row keeps its provenance."""
    stored = grifter().model_copy(update={"proposed_for": "Corin Vale"})
    again = validate_background(
        name="Salt-Road Grifter",
        skills=["sleight of hand", "deception"],  # order is not identity
        tool="Forgery Kit",
        feature="a different feature entirely",
        existing={stored.name: stored},
    )
    assert again.proposed_for == "Corin Vale"


def test_reusing_a_name_for_different_mechanics_is_refused():
    stored = grifter()
    with pytest.raises(BackgroundError, match="already has a background called"):
        validate_background(
            name="Salt-Road Grifter",
            skills=["athletics", "survival"],
            existing={stored.name: stored},
        )


# --- the book --------------------------------------------------------------


def test_the_book_round_trips_through_yaml(tmp_path):
    book = BackgroundBook()
    book.add(grifter())
    path = book.save(tmp_path / "backgrounds.yaml")

    reloaded = BackgroundBook.load(path)
    assert reloaded.names() == ["Salt-Road Grifter"]
    assert reloaded.get("salt-road grifter").tools == ("forgery kit",)


def test_an_absent_book_is_empty_rather_than_an_error(tmp_path):
    assert len(BackgroundBook.load(tmp_path / "nothing.yaml")) == 0


def test_adding_a_name_the_book_already_holds_changes_nothing():
    book = BackgroundBook()
    book.add(grifter())
    book.add(grifter().model_copy(update={"feature": "something else"}))
    assert len(book) == 1


# --- what a background actually grants -------------------------------------


def test_a_campaign_background_grants_skills_and_a_tool(repo):
    book = BackgroundBook()
    book.add(grifter())
    sheet = build_character(concept(), repo, book.get)

    assert sheet.proficiencies.skills[Skill.DECEPTION] is Proficiency.PROFICIENT
    assert sheet.proficiencies.skills[Skill.SLEIGHT_OF_HAND] is Proficiency.PROFICIENT
    assert "forgery kit" in sheet.proficiencies.tools


def test_a_background_language_lands_on_the_sheet(repo):
    book = BackgroundBook()
    book.add(
        validate_background(
            name="Harbour Translator",
            skills=["insight", "persuasion"],
            language="elvish",
            languages_known=repo.known_languages(),
        )
    )
    sheet = build_character(
        concept(background="Harbour Translator"), repo, book.get
    )
    assert "Elvish" in sheet.proficiencies.languages


def test_a_language_the_species_already_speaks_is_not_listed_twice(repo):
    """De-duplicated rather than refused: unlike a class skill pick, nothing choosable
    is lost, and refusing would make a reusable background unreusable."""
    book = BackgroundBook()
    book.add(
        validate_background(
            name="Common Tongue",
            skills=["insight", "persuasion"],
            language="common",
            languages_known=repo.known_languages(),
        )
    )
    sheet = build_character(concept(background="Common Tongue"), repo, book.get)
    assert sheet.proficiencies.languages.count("Common") == 1


def test_a_class_pick_duplicating_a_granted_skill_is_refused(repo):
    """P1.4's double-granting trap, now reachable through campaign content."""
    book = BackgroundBook()
    book.add(grifter())
    with pytest.raises(BuildError, match="already grants deception"):
        build_character(
            concept(skills=(Skill.DECEPTION, Skill.ATHLETICS)), repo, book.get
        )


def test_expertise_may_land_on_a_background_skill(repo):
    """5e says expertise is two of *your* skill proficiencies, not two of the class's."""
    book = BackgroundBook()
    book.add(grifter())
    sheet = build_character(
        Concept(
            name="Corin Vale",
            player="Kelly",
            species="Human",
            character_class="Rogue",
            priority=PRIORITY,
            skills=(Skill.STEALTH, Skill.INSIGHT, Skill.PERSUASION, Skill.INVESTIGATION),
            background="Salt-Road Grifter",
            expertise=("deception", "forgery kit"),
            languages=("dwarvish",),
        ),
        repo,
        book.get,
    )
    assert sheet.proficiencies.skills[Skill.DECEPTION] is Proficiency.EXPERTISE
    assert sheet.proficiencies.tools["forgery kit"] is Proficiency.EXPERTISE


def test_an_unknown_background_is_still_flavour(repo):
    """Every character built before any of this still loads, and still means something."""
    sheet = build_character(concept(background="Urchin"), repo)
    assert sheet.background == "Urchin"
    assert Skill.DECEPTION not in sheet.proficiencies.skills


def test_grant_issues_finds_a_campaign_background_the_sheet_ignored(repo):
    book = BackgroundBook()
    book.add(grifter())
    sheet = build_character(concept(), repo, book.get)
    stripped = sheet.model_copy(
        update={
            "proficiencies": sheet.proficiencies.model_copy(
                update={
                    "skills": {Skill.ATHLETICS: Proficiency.PROFICIENT},
                    "tools": {},
                }
            )
        }
    )

    issues = grant_issues(stripped, repo, book.get)
    assert any("deception" in issue for issue in issues)
    assert any("forgery kit" in issue for issue in issues)
    # Without the book the same sheet reports nothing about its background at all, which
    # is why `sheet validate` takes `--campaign`.
    assert not any("forgery kit" in issue for issue in grant_issues(stripped, repo))


# --- the interview ---------------------------------------------------------


def test_the_gm_writes_a_background_and_the_sheet_gets_it(repo):
    book = BackgroundBook()
    session = convo(repo, ["opener", GRIFTER], book=book, confirm=lambda _: True)
    session.open()
    reply = session.say("She grew up on the road.")

    assert reply.background is not None
    assert reply.background.name == "Salt-Road Grifter"
    assert reply.sheet.proficiencies.skills[Skill.SLEIGHT_OF_HAND] is Proficiency.PROFICIENT
    assert book.names() == ["Salt-Road Grifter"]
    assert "BACKGROUND" not in reply.text


def test_the_table_declining_sends_the_objection_to_the_gm_not_the_player(repo):
    """A decline is an engine objection like any other: the GM writes another, silently."""
    second = GRIFTER.replace("Salt-Road Grifter", "Coast Road Runner").replace(
        "skills: deception, sleight of hand", "skills: survival, persuasion"
    )
    answers = iter([False, True])
    book = BackgroundBook()
    session = convo(
        repo, ["opener", GRIFTER, second], book=book, confirm=lambda _: next(answers)
    )
    session.open()
    reply = session.say("She grew up on the road.")

    assert reply.error is None
    assert book.names() == ["Coast Road Runner"]
    assert reply.background.name == "Coast Road Runner"
    assert "declined" not in reply.text


def test_both_the_accepted_and_the_refused_are_logged(repo, tmp_path):
    """What a model invented and the humans rejected measures the model — if it is
    written down."""
    log = SessionLog.open(tmp_path)
    second = GRIFTER.replace("Salt-Road Grifter", "Coast Road Runner").replace(
        "skills: deception, sleight of hand", "skills: survival, persuasion"
    )
    answers = iter([False, True])
    session = convo(
        repo,
        ["opener", GRIFTER, second],
        book=BackgroundBook(),
        confirm=lambda _: next(answers),
        log=log,
    )
    session.open()
    session.say("She grew up on the road.")

    writes = [
        event
        for event in read_log(log.path)
        if event.type is EventType.BACKGROUND_WRITE
    ]
    assert [(w.name, w.confirmed, w.applied) for w in writes] == [
        ("Salt-Road Grifter", False, False),
        ("Coast Road Runner", True, True),
    ]
    assert writes[0].skills == ("deception", "sleight_of_hand")
    assert "[[BACKGROUND:" in writes[0].established_by


def test_finish_files_the_background_beside_the_canon(repo, campaigns_root):
    create_campaign("The Salt Road", players=["Kelly"])
    session = convo(repo, ["opener", GRIFTER], book=BackgroundBook(), confirm=lambda _: True)
    session.open()
    session.say("She grew up on the road.")

    _, canon_path, backgrounds_path = session.finish("the-salt-road")
    assert backgrounds_path is not None
    assert backgrounds_path.parent == canon_path.parent

    filed = load_campaign_backgrounds("the-salt-road")
    (background,) = list(filed)
    assert background.name == "Salt-Road Grifter"
    # Stamped at `finish`, because that is the first moment the character has a name.
    assert background.proposed_for == "Corin Vale"
    assert background.established is not None


def test_a_second_character_reuses_the_book_without_rewriting_it(repo, campaigns_root):
    create_campaign("The Salt Road", players=["Kelly"])
    first = convo(repo, ["opener", GRIFTER], book=BackgroundBook(), confirm=lambda _: True)
    first.open()
    first.say("She grew up on the road.")
    first.finish("the-salt-road")

    reused = GRIFTER.replace("name: Corin Vale", "name: Dess Marrow")
    asked = []
    second = convo(
        repo,
        ["opener", reused],
        book=load_campaign_backgrounds("the-salt-road"),
        confirm=lambda background: asked.append(background) or True,
    )
    second.open()
    reply = second.say("Same road, different woman.")

    assert asked == []  # nothing new was invented, so nobody was asked
    assert reply.background is None
    assert reply.sheet.proficiencies.skills[Skill.DECEPTION] is Proficiency.PROFICIENT
    assert len(second.backgrounds) == 1


def test_the_menu_lists_what_the_campaign_has_written(repo):
    from dndc.gm.creation import render_options

    book = BackgroundBook()
    book.add(grifter())
    options = render_options(repo, book)
    assert "**Acolyte** *(ruleset)*" in options
    assert "**Salt-Road Grifter** *(this campaign)*" in options
