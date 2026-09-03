"""P5.5: pronouns are recorded once, and nothing downstream guesses.

The finding this exists for is measurable rather than anecdotal. Across all fourteen
logs, restricted to sentences naming exactly one player character and nobody else:
Brother Hammond took masculine pronouns 10 times out of 10, and Corin Vale took feminine
ones 5 times out of 5 in play — but the chronicler, reading a transcript with no roster,
called her "he". One name carries the signal a guess is made from and the other does not,
which is exactly the failure mode a guess produces: reliable until it isn't, and wrong in
the layer furthest from the evening that established the answer.
"""

from __future__ import annotations

import pytest

from dndc.game.cli import _pronouns
from dndc.gm.chronicle import Chronicle, ChronicleEntry
from dndc.gm.context import CampaignContext, GMPromptBuilder, PartyMember
from dndc.gm.proposal import find_proposal
from dndc.gm.templates import load_template, placeholders, render_template
from dndc.memory.chronicle import Chronicler
from dndc.memory.recap import Recapper
from dndc.models.mock import MockBackend
from dndc.schema.npc import NPC, VoiceCard
from dndc.schema.sheet import CharacterSheet

from tests.test_chronicle import NARRATION, SUMMARY, session

CORIN = "she/her"


def sheet(pronouns: str = CORIN, **extra) -> CharacterSheet:
    fields = dict(
        name="Corin Vale",
        player="Kelly",
        pronouns=pronouns,
        species="Half-Elf",
        character_class="Rogue",
        abilities={"str": 8, "dex": 15, "con": 13, "int": 12, "wis": 10, "cha": 14},
        hit_points={"maximum": 9, "current": 9},
        armor_class=13,
    )
    fields.update(extra)
    return CharacterSheet(**fields)


def npc(name: str = "Halda Orrin", pronouns: str = "she/her") -> NPC:
    return NPC(id=name.lower().replace(" ", "-"), name=name, pronouns=pronouns,
               voice=VoiceCard(role="the waystation keeper"))


# --- the sheet is where the answer lives -----------------------------------


def test_a_sheet_records_pronouns():
    assert sheet().pronouns == CORIN


def test_a_sheet_without_them_says_nothing_rather_than_something():
    """Blank is a legitimate answer, and it must survive as blank all the way down —
    a default of "they/them" would be a guess wearing a safer coat."""
    assert sheet(pronouns="").pronouns == ""


# --- co-creation collects it -----------------------------------------------


def proposal(line: str) -> str:
    return (
        "[[PROPOSE:\n"
        "name: Corin Vale\n"
        f"{line}"
        "species: Half-Elf\n"
        "class: Rogue\n"
        "priority: cha, dex, con, wis, int, str\n"
        "ability_bonuses: dex, con\n"
        "skills: persuasion, stealth, insight, investigation\n"
        "expertise: stealth, thieves' tools\n"
        "languages: dwarvish\n"
        "]]"
    )


def test_the_gm_can_propose_pronouns():
    found = find_proposal(proposal("pronouns: she/her\n"), player="Kelly")

    assert found is not None
    assert found.concept.pronouns == "she/her"


@pytest.mark.parametrize("key", ["pronouns", "pronoun", "gender"])
def test_the_keys_a_model_actually_writes_all_land(key):
    found = find_proposal(proposal(f"{key}: they/them\n"), player="Kelly")

    assert found is not None and found.concept.pronouns == "they/them"


def test_a_proposal_without_the_line_is_still_valid():
    """Required fields are the ones the engine cannot build a sheet without. This is not
    one of them, and a character whose player has not said is a character who has not
    said."""
    found = find_proposal(proposal(""), player="Kelly")

    assert found is not None and found.concept.pronouns == ""


def test_free_text_is_kept_verbatim():
    found = find_proposal(proposal("pronouns: she/they\n"), player="Kelly")

    assert found is not None and found.concept.pronouns == "she/they"


def test_the_built_sheet_carries_what_the_concept_proposed():
    from dndc.rules.build import build_character
    from dndc.srd.repository import SRDRepository

    found = find_proposal(proposal("pronouns: she/her\n"), player="Kelly")
    assert found is not None

    assert build_character(found.concept, SRDRepository.load()).pronouns == "she/her"


# --- the GM prompt, every turn ---------------------------------------------


def test_the_party_block_carries_them():
    member = PartyMember.from_sheet(sheet())

    assert member.pronouns == CORIN
    assert CORIN in member.render()


def test_a_blank_leaves_the_line_alone():
    rendered = PartyMember.from_sheet(sheet(pronouns="")).render()

    assert "Corin Vale" in rendered
    assert "(" not in rendered.split("(played by Kelly)")[1]


def assembled(campaign: CampaignContext) -> str:
    request = GMPromptBuilder().build(campaign, "she looks around")
    return "\n".join([request.system, request.system_volatile])


def test_the_gm_is_told_every_turn():
    campaign = CampaignContext(name="The Salt Road", party=[PartyMember.from_sheet(sheet())])

    assert CORIN in assembled(campaign)


def test_the_gm_is_told_about_the_cast_too():
    """`npcs.yaml` has carried pronouns since P4.1 and the GM was never shown them — it
    was directing a they/them caravan master with nothing to go on but the name."""
    campaign = CampaignContext(name="The Salt Road", cast=[npc(pronouns="they/them")])

    assert "they/them" in assembled(campaign)


# --- the chronicle, which is where it actually went wrong ------------------


def chronicler(pronouns=None, **kwargs) -> tuple[Chronicler, MockBackend]:
    backend = MockBackend([SUMMARY], model="llama3.3:70b")
    kwargs.setdefault("party", ["Corin Vale"])
    return Chronicler(backend, pronouns=pronouns or {}, **kwargs), backend


def test_the_chronicler_is_told_how_to_refer_to_the_party():
    subject, backend = chronicler({"Corin Vale": CORIN})
    subject.record(session(), session="20260903-000000")

    assert f"Corin Vale ({CORIN})" in backend.calls[0].system


def test_the_chronicler_is_told_about_an_npc_the_session_named():
    subject, backend = chronicler({"Corin Vale": CORIN, "Halda Orrin": "she/her"})
    subject.record(session(), session="20260903-000000")

    assert "Halda Orrin (she/her)" in backend.calls[0].system


def test_an_npc_the_session_never_named_is_not_mentioned_at_all():
    """P4.1 on a third surface. The grounding check builds its vocabulary from the
    transcript, so a roster rendered into this prompt would be the check writing itself a
    permission slip — a name that reached the chronicler could then be used by it and
    would pass. Filtering here is what keeps those two things separate."""
    subject, backend = chronicler({"Corin Vale": CORIN, "Reeve Mattick": "he/him"})
    subject.record(session(), session="20260903-000000")

    assert "Mattick" not in backend.calls[0].system


def test_the_grounding_vocabulary_is_not_widened_by_knowing_a_pronoun():
    """The roster is for saying *how* to refer to someone, never *whether* they may be
    named. A summary that invents a person is still rejected when the invented person is
    in the pronoun map."""
    backend = MockBackend(
        ["Reeve Mattick closed the road and the party left Ashmill without an answer."],
        model="llama3.3:70b",
    )
    subject = Chronicler(backend, party=["Corin Vale"], pronouns={"Reeve Mattick": "he/him"})

    report = subject.record(session(), session="20260903-000000")

    assert report.entry is None
    assert "Mattick" in report.invented


def test_a_name_with_no_pronouns_recorded_is_left_bare():
    subject, backend = chronicler({})
    subject.record(session(), session="20260903-000000")

    assert "- Corin Vale\n" in backend.calls[0].system


def test_the_fold_is_told_too():
    """Compressing four paragraphs into one is exactly where a pronoun is picked up out
    of the wrong sentence."""
    entries = [
        ChronicleEntry(id=f"s{i}", summary=NARRATION, sessions=(f"2026080{i}-000000",))
        for i in range(1, 10)
    ]
    backend = MockBackend([SUMMARY], model="llama3.3:70b")
    subject = Chronicler(
        backend,
        chronicle=Chronicle(entries=entries),
        party=["Corin Vale"],
        pronouns={"Corin Vale": CORIN, "Halda Orrin": "she/her"},
    )

    subject.record(session(), session="20260903-000000")

    fold = backend.calls[-1].system
    assert len(backend.calls) == 2
    assert f"Corin Vale ({CORIN})" in fold
    assert "Halda Orrin (she/her)" in fold


# --- the recap, which is read out loud -------------------------------------


def recapper(pronouns=None) -> tuple[Recapper, MockBackend]:
    backend = MockBackend([f"PREVIOUSLY: {SUMMARY}\nWHERE: the yard at Ashmill"],
                          repeat_last=False)
    return Recapper(backend=backend, party=["Corin Vale"], pronouns=pronouns or {}), backend


def test_the_recap_is_told_how_to_refer_to_the_party():
    subject, backend = recapper({"Corin Vale": CORIN})
    subject.recap("The Salt Road", Chronicle(entries=[ChronicleEntry(id="s1", summary=SUMMARY)]))

    assert f"Corin Vale ({CORIN})" in backend.calls[0].system


def test_the_recap_leaves_an_unrecorded_name_bare():
    subject, backend = recapper({})
    subject.recap("The Salt Road", Chronicle(entries=[ChronicleEntry(id="s1", summary=SUMMARY)]))

    assert "- Corin Vale" in backend.calls[0].system
    assert "Corin Vale (" not in backend.calls[0].system


# --- what the game hands them ----------------------------------------------


def test_the_map_covers_party_and_cast_together():
    campaign = CampaignContext(
        name="The Salt Road",
        party=[PartyMember.from_sheet(sheet())],
        cast=[npc(pronouns="they/them")],
    )

    assert _pronouns(campaign) == {"Corin Vale": CORIN, "Halda Orrin": "they/them"}


def test_nobody_unrecorded_appears_in_the_map():
    """An absent key and an empty string are different downstream — one renders nothing,
    the other renders `Corin Vale ()`."""
    campaign = CampaignContext(
        name="The Salt Road",
        party=[PartyMember.from_sheet(sheet(pronouns=""))],
        cast=[npc(pronouns="")],
    )

    assert _pronouns(campaign) == {}


# --- the templates keep their placeholders ---------------------------------


@pytest.mark.parametrize("template", ["chronicle", "chronicle_fold", "recap"])
def test_every_template_that_names_people_still_renders(template):
    """The renderer is strict both ways, so a placeholder added to one chronicle template
    and forgotten in the other is a session that ends in a traceback rather than a
    chronicle. This is that regression, pinned."""
    values = {name: "-" for name in placeholders(load_template(template))}

    assert render_template(template, **values)
