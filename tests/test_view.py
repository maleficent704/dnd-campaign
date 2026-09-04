"""P6.2: what a player's device may be sent.

The assertions that matter here are made on the **serialised bytes**, not on the object.
An attribute nobody reads is not a leak; a string in the JSON that leaves the machine is.
Every other test in this file is scaffolding around that one idea.
"""

from __future__ import annotations

import pytest

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, PartyMember, SpokenLine, Turn
from dndc.schema.npc import NPC, VoiceCard
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)
from dndc.web import MemberView, TableView, TurnView, table_view
from dndc.web.view import NO_SCENE

SECRET = "The miller drowned the boy himself and the reeve helped him hide it."
UNDISCOVERED = "A sealed vault lies under the third landing of the undercroft."
BELIEF = "The guard is certain Corin took the crate and will not hear otherwise."


def sheet(name: str = "Corin Vale", pronouns: str = "she/her") -> CharacterSheet:
    return CharacterSheet(
        name=name,
        player="Kelly",
        pronouns=pronouns,
        species="Half-Elf",
        character_class="Rogue",
        abilities=AbilityScores(str=8, dex=15, con=13, int=12, wis=10, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=9, current=6),
        armor_class=14,
    )


def entry(scope: CanonScope, text: str, subject: str = "") -> CanonEntry:
    return CanonEntry(
        id=f"{scope.value}-{abs(hash(text)) % 9999}",
        scope=scope,
        text=text,
        subject=subject or None,
    )


def ledger(*entries: CanonEntry) -> CanonLedger:
    return CanonLedger(entries=list(entries))


def campaign(*entries: CanonEntry, scene: str = "the mill yard", turns=()) -> CampaignContext:
    context = CampaignContext(
        name="The Salt Road",
        scene=scene,
        party=[PartyMember.from_sheet(sheet())],
        ledger=ledger(*entries),
    )
    context.history = list(turns)
    return context


def turn(narration: str = "The wheel has stopped turning.", **extra) -> Turn:
    fields = dict(
        player_input="I look around",
        narration=narration,
        speaker="Kelly (Corin Vale)",
    )
    fields.update(extra)
    return Turn(**fields)


# --- the assertions this task exists for -----------------------------------


def test_a_gm_only_fact_is_not_in_the_bytes():
    view = table_view(campaign(entry(CanonScope.GM_ONLY, SECRET)))

    assert "drowned" not in view.model_dump_json()


def test_undiscovered_world_canon_is_not_in_the_bytes():
    """True, and nobody has found it. The ledger is the world, not the party's notes."""
    view = table_view(campaign(entry(CanonScope.WORLD, UNDISCOVERED)))

    assert "undercroft" not in view.model_dump_json()


def test_an_npc_belief_is_not_in_the_bytes():
    """P4.6 exists to let a character's mind change without anyone announcing it.
    Rendering the register onto the table's screen would undo that in one line."""
    view = table_view(campaign(entry(CanonScope.NPC_BELIEF, BELIEF, subject="the guard")))

    assert "certain" not in view.model_dump_json()


def test_what_the_party_established_does_reach_them():
    view = table_view(campaign(entry(CanonScope.PLAYER_KNOWN, "The mill wheel is stopped.")))

    assert view.known == ("The mill wheel is stopped.",)


def test_a_character_fact_reaches_them_too():
    """Co-creation's own output, about their own people (D-005)."""
    view = table_view(campaign(entry(CanonScope.CHARACTER, "Corin grew up on the coast road.")))

    assert "coast road" in view.model_dump_json()


def test_every_scope_at_once_and_only_two_survive():
    view = table_view(
        campaign(
            entry(CanonScope.GM_ONLY, SECRET),
            entry(CanonScope.WORLD, UNDISCOVERED),
            entry(CanonScope.NPC_BELIEF, BELIEF, subject="the guard"),
            entry(CanonScope.PLAYER_KNOWN, "The wheel is stopped."),
            entry(CanonScope.CHARACTER, "Corin grew up on the coast road."),
        )
    )

    assert len(view.known) == 2
    body = view.model_dump_json()
    assert "drowned" not in body and "undercroft" not in body and "certain" not in body


def test_a_superseded_fact_does_not_come_back():
    """`active()` is what `for_players` reads. A retired fact is history, not news."""
    live = entry(CanonScope.PLAYER_KNOWN, "The ferry runs at dawn.")
    dead = CanonEntry(
        id="player_known-old",
        scope=CanonScope.PLAYER_KNOWN,
        text="The ferry runs at noon.",
        superseded_by=live.id,
    )

    view = table_view(campaign(dead, live))

    assert view.known == ("The ferry runs at dawn.",)


# --- there is nowhere for a secret to sit ----------------------------------


def test_the_view_has_no_scope_field_anywhere():
    """The stronger claim than "we remembered to filter": a scope cannot travel, because
    no type here has anywhere to put one."""
    for model in (TableView, TurnView, MemberView):
        assert "scope" not in model.model_fields


def test_the_cast_is_absent_from_the_type_entirely():
    """An NPC's author notes and knowledge scopes are the GM's half of D-003. The only
    way a character appears on a device is by having said something out loud."""
    assert "cast" not in TableView.model_fields
    assert "npcs" not in TableView.model_fields


def test_an_unknown_field_is_refused_rather_than_carried():
    with pytest.raises(Exception):
        TableView(campaign="X", gm_notes=SECRET)


def test_a_view_cannot_be_edited_after_it_is_built():
    view = table_view(campaign())

    with pytest.raises(Exception):
        view.scene = SECRET


def test_the_cast_that_is_in_the_campaign_still_does_not_reach_a_device():
    """The GM's roster is on `CampaignContext` and rendered into its prompt every turn
    (P5.5 added pronouns to it). `table_view` reads the same object and takes none of it."""
    context = campaign()
    context.cast = [
        NPC(
            id="guard",
            name="the caravan guard",
            pronouns="he/him",
            voice=VoiceCard(role="a guard on the stalled caravan"),
            notes=SECRET,
        )
    ]

    assert "drowned" not in table_view(context).model_dump_json()


# --- the transcript --------------------------------------------------------


def test_narration_comes_from_the_window_where_the_tags_are_already_gone():
    """`Turn.narration` has been through `_clean`. `GMResponse.text` has not, and holds
    `[[CANON: gm_only — ...]]` in plain text — which is why nothing here reads one."""
    view = table_view(campaign(turns=[turn("The wheel has stopped.")]))

    assert view.turns[0].narration == "The wheel has stopped."


def test_the_opening_scene_is_attributed_to_nobody():
    """No player prompted it, and a screen saying Kelly said "(the session opens)" would
    be putting words in her mouth."""
    view = table_view(campaign(turns=[turn(opening=True, player_input="", speaker="")]))

    assert view.turns[0].opening is True
    assert view.turns[0].speaker == "" and view.turns[0].said == ""


def test_an_npc_line_travels_with_who_said_it():
    spoken = SpokenLine(speaker="the caravan guard", text="I saw you at the third wagon.")
    view = table_view(campaign(turns=[turn(dialogue=(spoken,))]))

    assert view.turns[0].dialogue[0].speaker == "the caravan guard"
    assert "third wagon" in view.turns[0].dialogue[0].text


def test_the_window_can_be_trimmed_without_lying_about_the_count():
    """A device showing the last three exchanges must not report the evening as three
    exchanges long."""
    view = table_view(campaign(turns=[turn() for _ in range(6)]), window=3)

    assert len(view.turns) == 3
    assert view.played == 6


def test_trimming_is_a_display_choice_and_the_default_is_everything():
    view = table_view(campaign(turns=[turn() for _ in range(6)]))

    assert len(view.turns) == 6


def test_a_window_of_nothing_is_still_a_valid_view():
    view = table_view(campaign(turns=[turn()]), window=0)

    assert view.turns == () and view.played == 1


# --- the party -------------------------------------------------------------


def test_the_party_carries_condition_and_pronouns_and_not_a_sheet():
    view = table_view(campaign())

    member = view.party[0]
    assert (member.name, member.pronouns) == ("Corin Vale", "she/her")
    assert (member.hp_current, member.hp_max) == (6, 9)
    assert "abilities" not in MemberView.model_fields


def test_whose_seat_it_is_travels_to_every_device():
    """Everyone is shown it; P6.4 decides who may act on it."""
    assert table_view(campaign(), acting="Corin Vale").acting == "Corin Vale"


# --- small honesty ---------------------------------------------------------


def test_a_campaign_with_no_scene_says_so_rather_than_showing_nothing():
    assert table_view(campaign(scene="")).scene == NO_SCENE


def test_an_empty_campaign_serialises_without_complaint():
    assert table_view(CampaignContext(name="Untitled")).model_dump_json()


# --- the guard that survives the next scope --------------------------------


def test_every_scope_this_build_knows_is_decided_one_way_or_the_other():
    """Pinned deliberately, the way D-008's family count is. A scope added later must be
    *decided* about rather than defaulting onto a screen — and because `for_players` is an
    allow-list, the default is already the safe one. This test is what turns that default
    into a conversation instead of a silence.
    """
    allowed = {CanonScope.PLAYER_KNOWN, CanonScope.CHARACTER}
    withheld = {CanonScope.GM_ONLY, CanonScope.WORLD, CanonScope.NPC_BELIEF}

    assert allowed | withheld == set(CanonScope), (
        "a new canon scope exists and nobody has said whether a player's device may see it"
    )

    context = campaign(*[entry(scope, f"a {scope.value} fact") for scope in CanonScope])
    body = table_view(context).model_dump_json()

    for scope in withheld:
        assert f"a {scope.value} fact" not in body
    for scope in allowed:
        assert f"a {scope.value} fact" in body


def test_the_two_allow_lists_disagree_about_player_known_and_that_is_the_point():
    """`for_npc` excludes `player_known` unconditionally (P4.1): what the party has
    established is not what the innkeeper has heard. `for_players` is the bucket it comes
    from. Neither is a filter over the other, and pinning the disagreement is what stops
    somebody later "simplifying" them into one list."""
    established = entry(CanonScope.PLAYER_KNOWN, "The party crossed at the ford.")
    book = ledger(established)
    npc = NPC(id="guard", name="the caravan guard", common_knowledge=True)

    assert established in book.for_players()
    assert established not in book.for_npc(npc)
