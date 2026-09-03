"""P4.5 — the GM directs, the character answers, and the line comes back established.

Two properties carry this file, and both are structural rather than a matter of the model
behaving:

**An NPC line never enters the assistant slot.** The GM must be able to read what a
character said and must never read it back as something *it* wrote — a GM that learns to
write Maren's dialogue is a GM holding `gm_only` canon speaking with her mouth, which is
the leak the whole tier exists to prevent.

**A missing character is visible.** Every way a direction can produce no line — no record,
past the per-turn cap, a dead local host, a blocked draft — is surfaced somewhere a human
will see it. Silence that looks like the GM simply chose not to have anyone speak is the
one failure mode nobody would ever notice.
"""

from __future__ import annotations

import pytest

from dndc.game.npcturn import NPCVoice
from dndc.game.turn import MAX_NPC_TURNS, TurnEngine
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, GMPromptBuilder, PartyMember, SpokenLine, Turn
from dndc.gm.context import render_transcript
from dndc.gm.gatekeeper import Judgement, Verdict
from dndc.gm.npcprompt import NPCPromptBuilder, NPCScene
from dndc.gm.speaktag import (
    SPEAK_PATTERN,
    find_speak_directions,
    strip_speak_directions,
)
from dndc.logging import read_log
from dndc.models.base import GMBackendError, Role
from dndc.models.mock import MockBackend
from dndc.schema.events import EventType
from dndc.schema.npc import NPC, VoiceCard

# --- the tag ---------------------------------------------------------------


def test_a_direction_carries_the_name_and_what_is_being_asked():
    found = find_speak_directions(
        "She sets down the glass.\n[[SPEAK: Maren | asked outright about the sheds]]"
    )
    assert [(d.name, d.direction) for d in found] == [
        ("Maren", "asked outright about the sheds")
    ]


@pytest.mark.parametrize("separator", ["|", "->", "→", "—", "=>"])
def test_any_separator_the_model_reaches_for_is_accepted(separator):
    """The producer is a language model. Losing a line of dialogue to an en dash would be
    a bad trade, and the tag is unambiguous however it is punctuated."""
    found = find_speak_directions(f"[[SPEAK: Maren {separator} about the tide]]")
    assert found[0].name == "Maren"
    assert found[0].direction == "about the tide"


def test_a_bare_name_is_a_direction_to_answer_what_was_just_said():
    found = find_speak_directions("[[SPEAK: Maren]]")
    assert found[0].name == "Maren"
    assert found[0].direction == ""


def test_the_tag_is_case_insensitive_and_survives_stray_punctuation():
    found = find_speak_directions("[[speak: Maren: | she is asked about the boat]]")
    assert found[0].name == "Maren"


def test_a_direction_may_span_lines():
    found = find_speak_directions(
        "[[SPEAK: Maren\n | she is asked whether\n she saw the boat]]"
    )
    assert found[0].name == "Maren"
    assert "saw the boat" in found[0].direction


def test_the_same_character_named_twice_speaks_once():
    """A character who answered, then answered again without having heard herself, is the
    conversation the claims ledger exists to prevent — and the GM repeating itself is not
    a reason to run two calls."""
    found = find_speak_directions("[[SPEAK: Maren | the sheds]] [[SPEAK: maren | the tide]]")
    assert len(found) == 1
    assert found[0].direction == "the sheds"


def test_a_nameless_direction_is_dropped():
    assert find_speak_directions("[[SPEAK: | tell them about it]]") == []


def test_directions_are_stripped_before_anyone_sees_the_narration():
    text = "She sets down the glass.\n\n[[SPEAK: Maren | the sheds]]\n"
    assert strip_speak_directions(text) == "She sets down the glass."


def test_the_pattern_does_not_swallow_ordinary_prose():
    assert find_speak_directions("She speaks: quietly, and only once.") == []
    assert SPEAK_PATTERN.search("[[CANON: world — she runs the inn]]") is None


# --- fixtures --------------------------------------------------------------


def maren(**fields) -> NPC:
    defaults = {
        "voice": VoiceCard(role="innkeeper at the Salt Wife", manner="dry, unhurried"),
        "knows_tags": ("harbour",),
        "location": "the taproom of the Salt Wife",
        "notes": "She is lying about the ledger.",
    }
    defaults.update(fields)
    return NPC.create("Maren", **defaults)


@pytest.fixture
def ledger() -> CanonLedger:
    book = CanonLedger()
    book.add(
        CanonEntry(
            id="world-harbour-fee",
            text="The harbourmaster takes a cut of every landing.",
            scope=CanonScope.WORLD,
            tags=("harbour",),
        )
    )
    return book


def campaign(cast=(), ledger=None) -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        scene="The taproom, late.",
        party=[PartyMember(name="Wren", player="Kelly")],
        ledger=ledger if ledger is not None else CanonLedger(),
        cast=list(cast),
    )


def engine_with(gm_says, npc_says="Couldn't tell you.", **kwargs) -> TurnEngine:
    voice = NPCVoice(backend=MockBackend([npc_says]))
    return TurnEngine(
        backend=MockBackend([gm_says] if isinstance(gm_says, str) else list(gm_says)),
        voice=voice,
        **kwargs,
    )


# --- directing -------------------------------------------------------------


def test_a_directed_character_answers_in_their_own_call(ledger):
    scene = campaign(cast=[maren()], ledger=ledger)
    engine = engine_with(
        "She sets down the glass. [[SPEAK: Maren | asked about the sheds]]",
        npc_says="Never been inside one.",
        campaign=scene,
    )

    result = engine.run("I ask about the sheds", player="Kelly")

    assert [reply.npc.name for reply in result.dialogue] == ["Maren"]
    assert result.dialogue[0].text == "Never been inside one."
    assert result.dialogue[0].direction == "asked about the sheds"
    # And the tag never reaches the table.
    assert "SPEAK" not in result.narration


def test_a_bare_direction_hands_the_character_the_players_own_words(ledger):
    """The GM declined to summarise, so the engine does not invent a summary — a
    paraphrase manufactured here would sit exactly where the GM's judgment belongs."""
    scene = campaign(cast=[maren()], ledger=ledger)
    voice = NPCVoice(backend=MockBackend(["Aye."]))
    engine = TurnEngine(
        backend=MockBackend(["She looks up. [[SPEAK: Maren]]"]), campaign=scene, voice=voice
    )

    engine.run("Have you seen the reeve tonight?", player="Kelly")

    npc_call = voice.backend.calls[-1]
    assert "Have you seen the reeve tonight?" in npc_call.messages[-1].content


def test_a_character_is_never_shown_the_gms_narration(ledger):
    """Measured live 2026-09-02 (f), and it is a leak vector rather than a nicety. GM prose
    is written by a model holding `gm_only` canon; piping it into an NPC prompt would
    defeat D-003's substitution rule with a convenience argument. It also parrots — shown
    the GM's guess at her own dialogue, she repeats it back nearly word for word."""
    scene = campaign(cast=[maren()], ledger=ledger)
    scene.scene = "The taproom, late."
    voice = NPCVoice(backend=MockBackend(["Aye."]))
    engine = TurnEngine(
        backend=MockBackend(
            ['She looks up. "The sheds are empty," she says. '
             "[[SPEAK: Maren | asked about the sheds]]"]
        ),
        campaign=scene,
        voice=voice,
    )

    engine.run("I ask about the sheds", player="Kelly")

    call = voice.backend.calls[-1]
    assembled = call.system + call.system_volatile + "".join(m.content for m in call.messages)
    assert "The sheds are empty" not in assembled
    assert "The taproom, late." in assembled


def test_a_character_with_no_record_is_reported_rather_than_improvised(ledger):
    """The roster and the prose disagreeing is an authoring bug, and one that only gets
    fixed if somebody is told. Nothing is invented to fill the gap."""
    scene = campaign(cast=[maren()], ledger=ledger)
    engine = engine_with("A stranger at the bar. [[SPEAK: Dess | about the tide]]", campaign=scene)

    result = engine.run("I turn to the stranger", player="Kelly")

    assert result.dialogue == []
    assert [d.name for d in result.unvoiced] == ["Dess"]


def test_no_more_than_two_characters_answer_in_one_turn(ledger):
    scene = campaign(
        cast=[maren(), NPC.create("Dess"), NPC.create("Halloran")], ledger=ledger
    )
    engine = engine_with(
        "[[SPEAK: Maren]] [[SPEAK: Dess]] [[SPEAK: Halloran]]", campaign=scene
    )

    result = engine.run("I ask the room", player="Kelly")

    assert len(result.dialogue) == MAX_NPC_TURNS
    assert [d.name for d in result.unvoiced] == ["Halloran"]


def test_the_turn_survives_a_dead_npc_seat(ledger):
    """The GM has already narrated and the players are mid-scene. A local box going away
    costs a line of dialogue; it must never cost the turn around it."""

    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("connection refused")

    scene = campaign(cast=[maren()], ledger=ledger)
    engine = TurnEngine(
        backend=MockBackend(["She looks up. [[SPEAK: Maren | the sheds]]"]),
        campaign=scene,
        voice=NPCVoice(backend=Dead()),
    )

    result = engine.run("I ask about the sheds", player="Kelly")

    assert result.narration.startswith("She looks up")
    assert result.dialogue == []
    assert "connection refused" in result.voice_errors[0]


def test_without_a_voice_a_direction_is_recorded_and_nothing_is_called(ledger):
    """`--no-npcs`, or a seat that would not build. Play continues with the GM voicing
    everyone in its own prose, which is what it did for three phases."""
    scene = campaign(cast=[maren()], ledger=ledger)
    engine = TurnEngine(
        backend=MockBackend(["[[SPEAK: Maren | the sheds]]"]), campaign=scene, voice=None
    )

    result = engine.run("I ask", player="Kelly")

    assert result.dialogue == []
    assert [d.name for d in result.unvoiced] == ["Maren"]


def test_an_opening_scene_may_hand_somebody_the_floor(ledger):
    scene = campaign(cast=[maren()], ledger=ledger)
    engine = engine_with(
        "The door bangs shut behind you. [[SPEAK: Maren | the travellers have just walked in]]",
        npc_says="Sit where you like.",
        campaign=scene,
    )

    result = engine.open_scene()

    assert result.dialogue[0].text == "Sit where you like."
    assert scene.history[-1].dialogue == (SpokenLine(speaker="Maren", text="Sit where you like."),)


# --- what the GM reads back ------------------------------------------------


def test_dialogue_reaches_the_gm_as_input_and_never_as_its_own_voice(ledger):
    """The property this whole design turns on. Maren's line has to be in the prompt, and
    it has to be in the *user* half of it — a GM that reads her dialogue back as its own
    past output learns to write her dialogue, and then it is speaking for her while
    holding the campaign's secrets."""
    scene = campaign(cast=[maren()], ledger=ledger)
    engine = engine_with(
        "She sets down the glass. [[SPEAK: Maren | the sheds]]",
        npc_says="Never been inside one.",
        campaign=scene,
    )
    engine.run("I ask about the sheds", player="Kelly")

    messages = GMPromptBuilder().build(
        scene, player_input="I ask again", speaker="Kelly"
    ).messages
    spoken = [m for m in messages if "Never been inside one." in m.content]
    assert spoken, "the line has to reach the GM at all"
    assert all(m.role is Role.USER for m in spoken)
    assert all(
        "Never been inside one." not in m.content
        for m in messages
        if m.role is Role.ASSISTANT
    )


def test_the_line_rides_one_turn_forward_into_the_live_prompt(ledger):
    scene = campaign(cast=[maren()], ledger=ledger)
    scene.record(
        Turn(
            player_input="I ask about the sheds",
            narration="She sets down the glass.",
            dialogue=(SpokenLine(speaker="Maren", text="Never been inside one."),),
        )
    )
    request = GMPromptBuilder().build(scene, player_input="I ask again", speaker="Kelly")

    assert "Never been inside one." in request.messages[-1].content
    assert request.messages[-1].role is Role.USER


def test_the_window_alternates_strictly_even_with_dialogue(ledger):
    """Consecutive same-role messages are a portability risk across two backends and one
    more to come. Carrying the line forward keeps the sequence a plain alternation."""
    scene = campaign(cast=[maren()], ledger=ledger)
    for index in range(3):
        scene.record(
            Turn(
                player_input=f"turn {index}",
                narration=f"narration {index}",
                dialogue=(SpokenLine(speaker="Maren", text=f"line {index}"),),
            )
        )
    roles = [m.role for m in scene.window()]
    assert roles == [Role.USER, Role.ASSISTANT] * 3


def test_a_blocked_line_enters_nothing(ledger):
    """The gate found something it could not repair. Nothing is shown, nothing is carried,
    and the GM is not told that a character was about to say something and then did not —
    which forecloses neither answer to the open question about what a block should cost."""

    class Blocking:
        def check(self, npc, ledger, draft):
            return Judgement(verdict=Verdict.BLOCKED, text="", draft=draft, reason="invents a name")

    scene = campaign(cast=[maren()], ledger=ledger)
    voice = NPCVoice(backend=MockBackend(["The reeve was here on Tuesday."]), gate=Blocking())
    engine = TurnEngine(
        backend=MockBackend(["She looks up. [[SPEAK: Maren | the reeve]]"]),
        campaign=scene,
        voice=voice,
    )

    result = engine.run("I ask about the reeve", player="Kelly")

    assert result.dialogue[0].text == ""
    assert scene.history[-1].dialogue == ()
    assert all("Tuesday" not in m.content for m in scene.window())


def test_the_session_reader_sees_what_the_characters_said():
    """The sweep and the chronicle read a session back. Most of what a village establishes
    is established out loud, so a reader that skipped dialogue would lose it."""
    turns = [
        Turn(
            player_input="I ask about the sheds",
            narration="She sets down the glass.",
            speaker="Kelly (Wren)",
            dialogue=(SpokenLine(speaker="Maren", text="Nobody's used them since the fire."),),
        )
    ]
    assert "Maren: Nobody's used them since the fire." in render_transcript(turns)


# --- the roster ------------------------------------------------------------


def test_the_gm_is_shown_who_speaks_for_themselves(ledger):
    state = GMPromptBuilder().campaign_state(campaign(cast=[maren()], ledger=ledger))
    assert "Maren" in state
    assert "innkeeper at the Salt Wife" in state
    assert "the taproom of the Salt Wife" in state


def test_the_gm_holds_the_authors_notes_and_the_character_never_does(ledger):
    """The boundary D-003 draws, in one assertion: the director is told she is lying, and
    the character being voiced is not."""
    npc = maren()
    gm_state = GMPromptBuilder().campaign_state(campaign(cast=[npc], ledger=ledger))
    npc_prompt = NPCPromptBuilder().build(npc, ledger, NPCScene(prompt="the sheds"))
    assembled = npc_prompt.system + npc_prompt.system_volatile

    assert "lying about the ledger" in gm_state
    assert "lying about the ledger" not in assembled


def test_an_empty_cast_says_so_rather_than_leaving_a_hole():
    state = GMPromptBuilder().campaign_state(campaign())
    assert "voice everyone in your own prose" in state


def test_the_gm_is_never_shown_what_a_character_knows(ledger):
    """The GM chooses who speaks; the ledger chooses what they know. A GM shown the scope
    would start writing directions that reach into it."""
    state = GMPromptBuilder().campaign_state(campaign(cast=[maren()], ledger=ledger))
    roster = state.split("Characters who speak for themselves")[1].split("\n## ")[0]
    assert "harbour" not in roster


# --- logging ---------------------------------------------------------------


def test_the_direction_is_logged_beside_what_was_said(tmp_path, ledger):
    """An NPC that names the tunnel unprompted and one that was *told* to talk about the
    tunnel are different failures. `text` alone cannot tell them apart."""
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    scene = campaign(cast=[maren()], ledger=ledger)
    voice = NPCVoice(backend=MockBackend(["Never been inside one."]), log=log)
    engine = TurnEngine(
        backend=MockBackend(["She looks up. [[SPEAK: Maren | asked about the sheds]]"]),
        campaign=scene,
        voice=voice,
        log=log,
    )
    engine.run("I ask about the sheds", player="Kelly")

    rows = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN]
    assert rows[-1].direction == "asked about the sheds"


def test_the_warm_up_is_logged_with_its_latency_and_speaks_to_nobody(tmp_path):
    """A warm-up that took a minute means a 40 GB model just loaded, and one that took
    200 ms means it was already there. Logged separately from any turn, so a session's
    first line can never again have a model load hidden inside its timing."""
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    voice = NPCVoice(backend=MockBackend(["ready"]), log=log)

    voice.warm_up()

    events = read_log(log.path)
    costs = [e for e in events if e.type is EventType.COST]
    assert len(costs) == 1
    assert costs[0].seat == "npc"
    # It is a seat event, not an utterance: the npc_turn stream is a research surface and
    # a fake line in it would be a character who never spoke.
    assert not [e for e in events if e.type is EventType.NPC_TURN]


def test_a_gm_call_records_how_long_it_took(tmp_path):
    from dndc.logging import SessionLog
    from dndc.models.base import GMResponse

    log = SessionLog.open(tmp_path)
    engine = TurnEngine(
        backend=MockBackend([GMResponse(text="The door opens.", model="m", duration_ms=1234)]),
        campaign=campaign(),
        log=log,
    )
    engine.run("I open the door", player="Kelly")

    costs = [e for e in read_log(log.path) if e.type is EventType.COST]
    assert costs[0].latency_ms == 1234
