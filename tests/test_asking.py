"""P6.5: the confirmations, answerable from either end of the house.

Three things stop an evening and wait for a person — items, canon proposals, the recap's
scene. All three were blocking `rich` prompts, which is why a browser could take a turn
but could not finish a session. The assertion that matters most here is the one about
silence: a browser closed mid-question must cost the table a keystroke, never the evening.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from dndc.game.asking import (
    CANON,
    INVENTORY,
    SCENE,
    Answer,
    Choice,
    Question,
    parse_selection,
    read,
)
from dndc.game.floor import Floor, Refusal
from dndc.gm.context import CampaignContext, PartyMember
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)
from dndc.web.mirror import Mirror
from dndc.web.view import table_view


def question(kind: str = CANON, n: int = 3, **extra) -> Question:
    fields = dict(
        kind=kind,
        prompt="file which?",
        choices=tuple(Choice(text=f"fact {i}") for i in range(1, n + 1)),
    )
    fields.update(extra)
    return Question(**fields)


def sheet(name: str = "Corin Vale") -> CharacterSheet:
    return CharacterSheet(
        name=name, player="Kelly", pronouns="she/her", species="Half-Elf",
        character_class="Rogue",
        abilities=AbilityScores(str=8, dex=15, con=13, int=12, wis=10, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=9, current=6), armor_class=14,
    )


def campaign() -> CampaignContext:
    return CampaignContext(name="The Salt Road", party=[PartyMember.from_sheet(sheet())])


# --- reading a reply --------------------------------------------------------


@pytest.mark.parametrize(
    "said, expected",
    [("all", {1, 2, 3}), ("", {1, 2, 3}), ("none", set()), ("1 3", {1, 3}), ("2", {2})],
)
def test_a_selection_is_read_the_way_it_is_typed(said, expected):
    assert read(question(), said).chosen == expected


def test_an_unreadable_reply_is_not_a_decision():
    """"" and "wat" must not both silently discard a session's worth of canon."""
    assert read(question(), "wat") is None


def test_out_of_range_numbers_are_dropped_rather_than_rejecting_the_reply():
    """Somebody who types `1 3 9` at a list of four meant one and three."""
    assert parse_selection("1 3 9", 4) == {1, 3}


# --- the scene question is the odd one --------------------------------------


def scene_q() -> Question:
    return Question(kind=SCENE, prompt="open here?", accepts_text=True,
                    choices=(Choice(text="the crossroads at Brakewater"),))


def test_an_empty_reply_accepts_the_proposed_scene():
    answer = read(scene_q(), "")

    assert answer.yes is True and answer.text == ""


def test_saying_no_keeps_the_old_scene():
    assert read(scene_q(), "n").yes is False


def test_anything_else_typed_is_the_new_scene():
    """The person answering is one of the two who were actually there. Making them retype
    a sentence into a yes/no box would be the interface arguing with them."""
    answer = read(scene_q(), "the mill road, an hour after dark")

    assert answer.yes is True
    assert answer.text == "the mill road, an hour after dark"


# --- silence ----------------------------------------------------------------


def test_silence_is_distinguishable_from_a_decline():
    """They do the same thing, and a log has to be able to tell them apart."""
    from dndc.game.asking import NOTHING, SILENCE

    assert SILENCE.answered is False and NOTHING.answered is True
    assert SILENCE.chosen == NOTHING.chosen == frozenset()


def test_silence_is_not_a_yes():
    assert Answer(answered=False).yes is False


# --- the floor's answering mode ---------------------------------------------


def test_an_answer_is_refused_when_nothing_is_being_asked():
    assert Floor().answer("all").refusal is Refusal.NOTHING_ASKED


def test_an_answer_is_taken_while_a_question_stands():
    floor = Floor()

    with floor.answering():
        assert floor.answer("1 3").accepted is True

    assert floor.next(timeout=0).text == "1 3"


def test_answering_is_not_gated_on_whose_turn_it_is():
    """A confirmation belongs to the table, not the acting player. Either of them may say
    whether an item goes on a sheet."""
    floor = Floor()

    with floor.answering():
        assert floor.answer("none").accepted is True


def test_a_turn_is_refused_while_the_table_is_being_asked_something():
    floor = Floor()

    with floor.answering():
        offer = floor.offer("Corin Vale", "I wade in", "Corin Vale", {"Corin Vale"})

    assert offer.refusal is Refusal.QUESTION_PENDING
    assert offer.reason == "answer the question first"


def test_a_question_that_raised_does_not_close_the_floor_forever():
    floor = Floor()

    with pytest.raises(RuntimeError):
        with floor.answering():
            raise RuntimeError("the device went away")

    assert floor.asking is False
    assert floor.offer("Corin Vale", "x", "Corin Vale", {"Corin Vale"}).accepted is True


def test_the_keyboard_can_still_answer():
    """A typed line and a posted one land on the same queue, so whoever replies first
    replies and the terminal is not a special case."""
    floor = Floor()

    with floor.answering():
        floor.typed("all")

    assert floor.next(timeout=0).text == "all"


# --- what the devices see ---------------------------------------------------


def test_a_question_reaches_every_watching_device():
    mirror = Mirror()
    watcher = mirror.subscribe()

    mirror.asking(question(kind=INVENTORY))

    message = json.loads(watcher.queue.get_nowait())
    assert message["kind"] == "asking"
    assert message["question"]["kind"] == "inventory"
    assert [c["text"] for c in message["question"]["choices"]] == ["fact 1", "fact 2", "fact 3"]


def test_a_device_arriving_mid_question_is_shown_it():
    """Otherwise a phone picked up while the evening waits shows a screen that looks idle."""
    mirror = Mirror()
    mirror.show(table_view(campaign()))
    mirror.asking(question())

    assert mirror.snapshot()["question"]["prompt"] == "file which?"


def test_the_question_comes_down_when_it_is_answered():
    mirror = Mirror()
    mirror.asking(question())

    mirror.answered()

    assert mirror.snapshot()["question"] is None


def test_the_alternates_travel_so_nothing_is_hidden():
    """Grouping decides what sits under what, not what the table gets to see."""
    mirror = Mirror()
    watcher = mirror.subscribe()

    mirror.asking(
        Question(kind=CANON, prompt="file which?",
                 choices=(Choice(text="The rail wobbles.", detail=("The rail is loose.",)),))
    )

    body = json.loads(watcher.queue.get_nowait())
    assert body["question"]["choices"][0]["detail"] == ["The rail is loose."]


def test_a_note_travels_with_the_question():
    """A proposal for nobody is logged and shown, not silently dropped."""
    mirror = Mirror()

    mirror.asking(question(notes=("iron key -> Ordell — no such character",)))

    assert "Ordell" in json.dumps(mirror.snapshot()["question"]["notes"])


# --- over HTTP --------------------------------------------------------------

pytest.importorskip("fastapi", reason="the `web` extra is optional")


def served():
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    mirror = Mirror()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    floor = Floor()
    return TestClient(build_app(mirror, floor)), mirror, floor


def test_an_answer_posted_while_a_question_stands_is_accepted():
    client, mirror, floor = served()
    mirror.asking(question())

    with floor.answering():
        answer = client.post("/api/answer", json={"text": "1 3"})

    assert answer.status_code == 202
    assert floor.next(timeout=0).text == "1 3"


def test_an_answer_to_nothing_is_refused_with_a_reason():
    client, _, _ = served()

    answer = client.post("/api/answer", json={"text": "all"})

    assert answer.status_code == 409
    assert answer.json()["refusal"] == "nothing_asked"


def test_a_turn_posted_during_a_question_is_refused():
    client, _, floor = served()

    with floor.answering():
        answer = client.post("/api/turn", json={"character": "Corin Vale", "text": "I wade in"})

    assert answer.status_code == 409
    assert answer.json()["refusal"] == "question_pending"


def test_a_spectator_link_cannot_answer_either():
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    client = TestClient(build_app(Mirror(), None))

    assert client.post("/api/answer", json={"text": "all"}).status_code == 404


# --- the whole round trip ---------------------------------------------------


class Recording:
    """Enough of a table to drive `MirrorTable.ask` without a terminal."""

    def __init__(self, console_notices: list) -> None:
        self.items = None
        self.console = None
        self.cfg = None
        self.notices = console_notices

    def show_question(self, q) -> None:
        pass

    def notice(self, text: str) -> None:
        self.notices.append(text)


def mirror_table(floor: Floor, mirror: Mirror):
    from dndc.game.cli import MirrorTable

    notices: list[str] = []
    return MirrorTable(Recording(notices), mirror, None, floor), notices


def test_an_answer_from_a_device_comes_back_to_the_session():
    """The round trip that P6.5 exists for: the evening stops, a phone answers, it goes on."""
    mirror, floor = Mirror(), Floor()
    table, _ = mirror_table(floor, mirror)

    def reply() -> None:
        for _ in range(200):
            if floor.asking:
                floor.answer("1 3")
                return
            time.sleep(0.01)

    threading.Thread(target=reply, daemon=True).start()
    answer = table.ask(question())

    assert answer.answered is True
    assert answer.chosen == frozenset({1, 3})


def test_nobody_answering_costs_a_keystroke_and_not_the_evening():
    """The assertion this task exists for."""
    from dndc.game import cli

    mirror, floor = Mirror(), Floor()
    table, notices = mirror_table(floor, mirror)

    original = cli.ANSWER_TIMEOUT
    cli.ANSWER_TIMEOUT = 0.05
    try:
        answer = table.ask(question())
    finally:
        cli.ANSWER_TIMEOUT = original

    assert answer.answered is False
    assert answer.chosen == frozenset()
    assert any("nobody answered" in note for note in notices)


def test_the_question_is_taken_down_even_when_nobody_answered():
    from dndc.game import cli

    mirror, floor = Mirror(), Floor()
    table, _ = mirror_table(floor, mirror)

    original = cli.ANSWER_TIMEOUT
    cli.ANSWER_TIMEOUT = 0.05
    try:
        table.ask(question())
    finally:
        cli.ANSWER_TIMEOUT = original

    assert mirror.snapshot()["question"] is None
    assert floor.asking is False
