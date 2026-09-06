"""P6.3: the read-only mirror, and the one path to a device that skips the view model.

`web/view.py` guarantees a `gm_only` fact cannot reach a browser because its types have
nowhere to put one. Live narration goes around that entirely — it arrives raw off the
model, `[[CANON: gm_only — ...]]` and all, and never passes through those types. The
assertions about `narrate` are the ones this file exists for.
"""

from __future__ import annotations

import json

import pytest

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, PartyMember
from dndc.gm.tagstream import TagStream
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)
from dndc.web.lifecycle import Held
from dndc.web.mirror import BACKLOG, Mirror
from dndc.web.view import table_view

SECRET = "[[CANON: gm_only — The miller drowned the boy himself.]]"


def sheet(name: str = "Corin Vale") -> CharacterSheet:
    return CharacterSheet(
        name=name, player="Kelly", pronouns="she/her", species="Half-Elf",
        character_class="Rogue",
        abilities=AbilityScores(str=8, dex=15, con=13, int=12, wis=10, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=9, current=6), armor_class=14,
    )


def campaign(*entries) -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        scene="the mill yard",
        party=[PartyMember.from_sheet(sheet())],
        ledger=CanonLedger(entries=list(entries)),
    )


def drain(watcher) -> list[dict]:
    out = []
    while not watcher.queue.empty():
        out.append(json.loads(watcher.queue.get_nowait()))
    return out


# --- the tag filter, which is now shared ------------------------------------


def test_a_machine_tag_never_leaves_the_stream():
    stream = TagStream()
    shown = "".join(stream.feed(char) for char in f"He stops. {SECRET} The door opens.")

    assert "gm_only" not in shown
    assert "drowned" not in shown
    assert shown.strip() == "He stops. The door opens."


def test_ordinary_brackets_still_come_through():
    """The filter is on `[[`, so prose is untouched."""
    stream = TagStream()

    assert "".join(stream.feed(c) for c in "a [sic] note") + stream.finish() == "a [sic] note"


def test_a_half_written_tag_is_held_rather_than_shown():
    """The stream must decide about a character before it knows what follows."""
    stream = TagStream()

    assert stream.feed("the door [[CAN") == "the door "
    assert stream.feed("ON: world — it is oak]] opens") == "opens"


def test_the_space_a_tag_was_sitting_in_does_not_become_two():
    """The whitespace before a tag has already gone through, so the whitespace after it
    is swallowed. Otherwise every stripped tag leaves a visible gap mid-sentence."""
    stream = TagStream()
    shown = "".join(stream.feed(c) for c in "he pauses [[FACT: he is lying]] and turns")

    assert shown == "he pauses and turns"


def test_a_stream_that_ends_mid_tag_releases_nothing():
    """A truncated reply must not spill half a tag onto a screen."""
    stream = TagStream()
    stream.feed("he pauses [[CANON: gm_only — the mill")

    assert "mill" not in stream.finish()


def test_a_stream_that_ends_on_a_real_bracket_releases_it():
    stream = TagStream()
    stream.feed("a note [")

    assert stream.finish() == "["


def test_finishing_twice_produces_nothing_the_second_time():
    """An NPC line interrupting the GM's prose finishes the stream mid-reply."""
    stream = TagStream()
    stream.feed("tail [")

    assert stream.finish() == "[" and stream.finish() == ""


# --- what a watching device is sent -----------------------------------------


def test_a_secret_in_the_live_stream_does_not_reach_a_watcher():
    """The assertion this task exists for."""
    mirror = Mirror()
    watcher = mirror.subscribe()

    for char in f"The wheel is still. {SECRET} He looks away.":
        mirror.narrate(char)
    mirror.settle()

    body = json.dumps(drain(watcher))
    assert "drowned" not in body and "gm_only" not in body


def test_the_snapshot_of_a_turn_in_flight_is_filtered_too():
    """A phone connecting mid-sentence gets the accumulated text, not the raw text."""
    mirror = Mirror()
    mirror.narrate(f"She turns. {SECRET} ")

    assert "drowned" not in json.dumps(mirror.snapshot())


def test_a_settled_view_replaces_what_was_pending():
    """Pending text was a preview of the narration that has now arrived. Keeping both
    would show the paragraph twice."""
    mirror = Mirror()
    mirror.narrate("She turns.")
    mirror.show(table_view(campaign()))

    assert mirror.snapshot()["pending"] == ""


def test_the_withheld_ledger_does_not_reach_a_watcher_either():
    """The view model's guarantee, checked through the transport that carries it."""
    mirror = Mirror()
    watcher = mirror.subscribe()
    secret = CanonEntry(id="gm_only-1", scope=CanonScope.GM_ONLY, text="The reeve helped.")

    mirror.show(table_view(campaign(secret)))

    assert "reeve" not in json.dumps(drain(watcher))


def test_an_npc_line_carries_a_name_and_words_and_nothing_else():
    mirror = Mirror()
    watcher = mirror.subscribe()

    mirror.spoke("the caravan guard", "I saw you at the third wagon.")

    line = drain(watcher)[0]
    assert set(line) == {"kind", "speaker", "text"}


# --- watchers ---------------------------------------------------------------


def test_everyone_watching_gets_the_same_thing():
    mirror = Mirror()
    kelly, sam = mirror.subscribe(), mirror.subscribe()

    mirror.show(table_view(campaign()))

    assert drain(kelly) == drain(sam)


def test_a_device_that_stops_reading_is_dropped_rather_than_waited_for():
    """The evening belongs to the people in the room, not to a phone left on the sofa."""
    mirror = Mirror()
    mirror.subscribe()

    for _ in range(BACKLOG + 5):
        mirror.note("still here")

    assert mirror.watching == 0


def test_dropping_one_device_does_not_disturb_another():
    mirror = Mirror()
    stalled, live = mirror.subscribe(), mirror.subscribe()
    for _ in range(BACKLOG + 5):
        mirror.note("filling up")
        drain(live)

    assert mirror.watching == 1
    assert stalled.queue.full()


def test_a_device_that_leaves_stops_being_written_to():
    mirror = Mirror()
    watcher = mirror.subscribe()

    mirror.unsubscribe(watcher)
    mirror.note("after you left")

    assert drain(watcher) == []


def test_unsubscribing_twice_is_not_an_error():
    mirror = Mirror()
    watcher = mirror.subscribe()

    mirror.unsubscribe(watcher)
    mirror.unsubscribe(watcher)

    assert mirror.watching == 0


def test_a_mirror_nobody_is_watching_still_works():
    """A session started with --serve and never opened must behave exactly as one
    started without it."""
    mirror = Mirror()

    mirror.narrate("nobody is here")
    mirror.show(table_view(campaign()))
    mirror.ended()

    assert mirror.watching == 0


def test_a_device_connecting_from_cold_can_draw_the_whole_screen():
    mirror = Mirror()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    mirror.narrate("She steps into the yard.")
    mirror.spoke("the miller", "You're late.")

    snapshot = mirror.snapshot()
    assert snapshot["table"]["acting"] == "Corin Vale"
    assert snapshot["pending"] == "She steps into the yard."
    assert snapshot["spoken"] == [{"speaker": "the miller", "text": "You're late."}]


def test_a_snapshot_before_anything_has_happened_is_empty_rather_than_broken():
    assert Mirror().snapshot()["table"] is None


# --- the HTTP surface -------------------------------------------------------

fastapi = pytest.importorskip("fastapi", reason="the `web` extra is optional")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    mirror = Mirror()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    return TestClient(build_app(Held(mirror))), mirror


def test_the_page_is_served_and_needs_no_build_step(client):
    page = client[0].get("/")

    assert page.status_code == 200
    assert "<!doctype html>" in page.text.lower()
    assert "<script" in page.text


def test_the_table_endpoint_returns_the_view(client):
    body = client[0].get("/api/table").json()

    assert body["table"]["campaign"] == "The Salt Road"
    assert body["table"]["acting"] == "Corin Vale"


def test_there_is_no_way_to_change_anything(client):
    """Read-only in the strong sense: P6.4 adds the write path, and until then a device
    connected to this can watch an evening and do nothing else."""
    app = client[0].app
    methods = {method for route in app.routes for method in getattr(route, "methods", set())}

    assert methods <= {"GET", "HEAD"}


@pytest.mark.parametrize("path", ["/api/turn", "/api/act", "/api/scene"])
def test_a_write_route_does_not_exist_yet(client, path):
    assert client[0].post(path).status_code == 404


def frames(client) -> list[dict]:
    """Every SSE payload the stream produced before it closed.

    The session is ended first so the stream terminates — which is the behaviour, not a
    test convenience: a browser left showing a live screen for a finished evening is
    worse than one showing none.
    """
    body = client.get("/api/events").text
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_the_event_stream_opens_with_a_snapshot(client):
    """So a device connecting mid-turn draws a correct screen rather than an empty one
    that fills in from the next event onward."""
    api, mirror = client
    mirror.ended()

    first = frames(api)[0]
    assert first["table"]["campaign"] == "The Salt Road"


def test_the_stream_says_it_is_an_event_stream(client):
    api, mirror = client
    mirror.ended()

    with api.stream("GET", "/api/events") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["cache-control"] == "no-cache"


def test_the_stream_closes_when_the_evening_does(client):
    api, mirror = client
    mirror.ended()

    assert frames(api)[-1] == {"kind": "ended"}


def test_a_device_arriving_after_the_end_is_told_rather_than_left_waiting(client):
    """Otherwise a phone that reconnects at midnight waits all night on a session that
    finished at ten, showing a screen that looks live."""
    api, mirror = client
    mirror.ended()

    assert frames(api)[-1]["kind"] == "ended"
    assert mirror.over is True
