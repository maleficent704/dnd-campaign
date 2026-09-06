"""P6.4: taking a turn from a browser, and the rule about who may.

The load-bearing assertion is that a submission does not *run* anything. It puts a line on
a queue and returns; the play loop picks it up on its own thread. Every piece of campaign
state this project owns — the engine, the canon store, the save point — is single-threaded
by construction, and a turn run from a request handler would be a race against the
campaign itself.
"""

from __future__ import annotations

import json

import pytest

from dndc.game.floor import TERMINAL, WEB, Floor, Refusal
from dndc.gm.context import CampaignContext, PartyMember
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)
from dndc.web.lifecycle import Held
from dndc.web.mirror import Mirror
from dndc.web.view import table_view

PARTY = {"Corin Vale", "Brother Hammond"}


def sheet(name: str = "Corin Vale") -> CharacterSheet:
    return CharacterSheet(
        name=name, player="Kelly", pronouns="she/her", species="Half-Elf",
        character_class="Rogue",
        abilities=AbilityScores(str=8, dex=15, con=13, int=12, wis=10, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=9, current=6), armor_class=14,
    )


def campaign() -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        scene="the mill yard",
        party=[PartyMember.from_sheet(sheet(name)) for name in sorted(PARTY)],
    )


def offer(floor: Floor, character="Corin Vale", text="I look around", acting="Corin Vale"):
    return floor.offer(character=character, text=text, acting=acting, party=PARTY)


# --- who may speak ----------------------------------------------------------


def test_the_acting_character_may_speak():
    floor = Floor()

    assert offer(floor).accepted is True
    assert floor.next(timeout=0).text == "I look around"


def test_somebody_else_is_refused_and_told_why():
    """Silently queueing it would show a player their sentence vanishing into an evening
    that had already moved on."""
    answer = offer(Floor(), character="Brother Hammond")

    assert answer.accepted is False
    assert answer.refusal is Refusal.NOT_YOUR_TURN
    assert answer.reason == "it is not your turn"


def test_a_name_not_in_the_party_is_refused():
    assert offer(Floor(), character="Ordell").refusal is Refusal.NO_SUCH_CHARACTER


def test_a_name_is_matched_however_it_is_capitalised():
    """A phone that remembered "corin vale" is the same person."""
    assert offer(Floor(), character="corin vale").accepted is True


def test_an_empty_submission_is_refused_rather_than_queued():
    assert offer(Floor(), text="   ").refusal is Refusal.NOTHING_SAID


def test_a_refused_line_does_not_reach_the_queue():
    floor = Floor()

    offer(floor, character="Brother Hammond")

    assert floor.waiting == 0


# --- one turn at a time -----------------------------------------------------


def test_a_second_line_is_refused_while_the_gm_is_answering():
    floor = Floor()

    with floor.taking_a_turn():
        answer = offer(floor)

    assert answer.refusal is Refusal.TURN_IN_FLIGHT


def test_the_floor_reopens_when_the_turn_is_over():
    floor = Floor()
    with floor.taking_a_turn():
        pass

    assert offer(floor).accepted is True


def test_a_turn_that_raised_does_not_close_the_floor_for_the_evening():
    """The one thing that must never happen."""
    floor = Floor()

    with pytest.raises(RuntimeError):
        with floor.taking_a_turn():
            raise RuntimeError("the seat went away")

    assert floor.busy is False
    assert offer(floor).accepted is True


# --- the keyboard is not the web -------------------------------------------


def test_a_typed_line_is_always_taken():
    """Somebody in the room typed it; telling them "not now" would be answering for the
    table. The loop decides what to do with it."""
    floor = Floor()

    with floor.taking_a_turn():
        floor.typed("/quit")

    assert floor.next(timeout=0).text == "/quit"


def test_lines_remember_where_they_came_from():
    floor = Floor()
    floor.typed("I wade in")
    offer(floor)

    assert [line.source for line in (floor.next(0), floor.next(0))] == [TERMINAL, WEB]


def test_a_web_line_carries_who_said_it_and_a_typed_one_does_not():
    """The loop already knows whose seat it is when somebody types."""
    floor = Floor()
    floor.typed("I wade in")
    offer(floor)

    assert floor.next(0).character == ""
    assert floor.next(0).character == "Corin Vale"


def test_lines_come_out_in_the_order_they_went_in():
    floor = Floor()
    floor.typed("first")
    offer(floor, text="second")
    floor.typed("third")

    assert [floor.next(0).text for _ in range(3)] == ["first", "second", "third"]


def test_waiting_on_an_empty_floor_gives_up_rather_than_blocking():
    """The loop's timeout is what lets it notice a terminal that has gone away."""
    assert Floor().next(timeout=0.01) is None


# --- over HTTP --------------------------------------------------------------

pytest.importorskip("fastapi", reason="the `web` extra is optional")


def served(writable: bool = True):
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    mirror = Mirror()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    floor = Floor() if writable else None
    return TestClient(build_app(Held(mirror, floor))), mirror, floor


def test_a_turn_posted_by_the_acting_player_is_accepted():
    client, _, floor = served()

    answer = client.post("/api/turn", json={"character": "Corin Vale", "text": "I wade in"})

    assert answer.status_code == 202
    assert floor.next(timeout=0).text == "I wade in"


def test_posting_does_not_run_the_turn():
    """It queues a line and returns. The play loop is the only thing that runs turns."""
    client, _, floor = served()

    client.post("/api/turn", json={"character": "Corin Vale", "text": "I wade in"})

    assert floor.waiting == 1


def test_a_turn_out_of_seat_comes_back_as_a_conflict_with_a_reason():
    client, _, _ = served()

    answer = client.post("/api/turn", json={"character": "Brother Hammond", "text": "hi"})

    assert answer.status_code == 409
    assert answer.json() == {
        "accepted": False, "refusal": "not_your_turn", "reason": "it is not your turn",
    }


def test_the_gating_uses_what_the_devices_were_told():
    """Asking the session instead would let a browser be refused for a reason no screen
    had shown it yet."""
    client, mirror, _ = served()

    mirror.show(table_view(campaign(), acting="Brother Hammond"))

    assert client.post("/api/turn", json={"character": "Corin Vale", "text": "x"}).status_code == 409
    assert client.post("/api/turn", json={"character": "Brother Hammond", "text": "x"}).status_code == 202


def test_a_spectator_link_has_no_write_route_at_all():
    """Not a refusal — an absence. A device cannot tell "not allowed" from "not built",
    which is the honest shape for a read-only server."""
    client, _, _ = served(writable=False)

    assert client.post("/api/turn", json={"character": "Corin Vale", "text": "x"}).status_code == 404


def test_the_server_says_whether_it_takes_turns():
    """So a spectator page never offers a box that every submission will be refused from,
    and does not have to find out by making a request designed to fail."""
    assert served(writable=True)[0].get("/api/table").json()["writable"] is True
    assert served(writable=False)[0].get("/api/table").json()["writable"] is False


def test_the_stream_says_it_too():
    client, mirror, _ = served()
    mirror.ended()

    body = client.get("/api/events").text
    first = json.loads([l for l in body.splitlines() if l.startswith("data: ")][0][6:])

    assert first["writable"] is True


def test_a_malformed_body_is_refused_rather_than_crashing():
    client, _, _ = served()

    assert client.post("/api/turn", json={}).status_code == 409


def test_reading_is_still_possible_on_a_writable_server():
    """P6.3's whole surface has to survive P6.4."""
    client, _, _ = served()

    assert client.get("/").status_code == 200
    assert client.get("/api/table").json()["table"]["campaign"] == "The Salt Road"
