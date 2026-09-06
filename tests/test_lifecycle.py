"""P6.7b-iii: a server that outlives its evenings.

Until now the evening was the process. These are the tests for the other posture — a
server that boots with nobody playing, is asked to start one, runs it, and is still
there afterwards ready to be asked again.

Everything here is offline and synthetic on purpose: `build` and `run` are injected, so
what is under test is the lifecycle's own state machine rather than the campaign engine,
which has its own suite. The one thing that is *not* synthetic is the mirror, because
the bug this class most easily has is about mirrors.
"""

from __future__ import annotations

import argparse
import threading
import time

import pytest

from dndc.config import load_config
from dndc.game.evening import Closed
from dndc.game.floor import Floor
from dndc.game.setup import QuietHerald, SetupError
from dndc.web.lifecycle import IDLE, PLAYING, STARTING, Held, Lifecycle
from dndc.web.mirror import Mirror

WAIT = 2.0


def until(condition, what: str) -> None:
    """Wait for a threaded lifecycle to settle, or say what it never did."""
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError(f"never {what}")


def args_for(**overrides) -> argparse.Namespace:
    settled = dict(campaign=None, no_sweep=True, no_chronicle=True, watch_only=False)
    settled.update(overrides)
    return argparse.Namespace(**settled)


class Fake:
    """A stand-in evening: something to hand `run`, with the attributes it reads."""

    def __init__(self) -> None:
        self.session = object()
        self.items = object()
        self.engine = object()
        self.campaign = object()


def lifecycle(*, build=None, run=None, args=None, **kwargs) -> Lifecycle:
    return Lifecycle(
        load_config(),
        args or args_for(),
        table_for=lambda evening, mirror, floor: object(),
        herald=QuietHerald(),
        build=build or (lambda cfg, a, herald: Fake()),
        run=run or (lambda *a, **k: Closed(opened=True)),
        **kwargs,
    )


# --- the state machine -----------------------------------------------------


def test_a_server_with_nothing_playing_says_so():
    manager = lifecycle()

    assert manager.phase == IDLE
    assert manager.floor is None
    assert manager.mirror is not None  # never None: a route should not have to branch
    assert manager.state()["phase"] == IDLE


def test_an_evening_runs_and_the_server_is_still_there_afterwards():
    """The whole point. `_cmd_play` could not do the second half of this sentence."""
    running = threading.Event()
    release = threading.Event()

    def run(*a, **k):
        running.set()
        release.wait(WAIT)
        return Closed(opened=True)

    manager = lifecycle(run=run)
    assert manager.start("salt-road").accepted

    until(running.is_set, "started running")
    until(lambda: manager.phase == PLAYING, "reached playing")
    assert manager.floor is not None
    assert manager.state()["campaign"] == "salt-road"

    release.set()
    until(lambda: manager.phase == IDLE, "went back to idle")
    assert manager.floor is None
    assert manager.state()["campaign"] == ""


def test_a_second_evening_is_refused_while_one_is_running():
    """One at a time is a rule, not a limitation: two evenings would be two writers on
    one canon ledger, and every piece of campaign state here is single-threaded."""
    release = threading.Event()
    manager = lifecycle(run=lambda *a, **k: (release.wait(WAIT), Closed(True))[1])

    assert manager.start("salt-road").accepted
    until(lambda: manager.phase in (STARTING, PLAYING), "began")

    second = manager.start("ford-crossing")
    assert second.accepted is False
    assert "already" in second.reason
    release.set()


def test_an_evening_needs_a_name():
    refused = lifecycle().start("   ")

    assert refused.accepted is False
    assert "campaign" in refused.reason


def test_the_next_evening_gets_a_mirror_of_its_own():
    """The bug this class is most likely to have, and the reason `_idle` exists.

    A `Mirror` is one-shot: once it has said the evening ended, everything that
    subscribes to it is told so immediately. That is right for a process about to exit
    and a reconnect loop for one that is not — a browser would connect, be told the
    evening was over, close, and come back three seconds later, forever.
    """
    manager = lifecycle()
    first = manager.mirror

    assert manager.start("salt-road").accepted
    until(lambda: manager.phase == IDLE, "finished the first evening")
    second = manager.mirror

    assert second is not first
    assert second.over is False, "a reconnecting browser would be told it had missed it"


def test_the_evening_that_ran_was_told_it_ended():
    """The finished mirror is ended and the fresh one is not — the two must not be
    confused, because ending the fresh one is what causes the reconnect loop above."""
    manager = lifecycle()
    started = None

    assert manager.start("salt-road").accepted
    started = manager.mirror
    until(lambda: manager.phase == IDLE, "finished")

    assert started.over is True
    assert manager.mirror.over is False


# --- when it goes wrong ----------------------------------------------------


def test_a_campaign_that_will_not_load_leaves_the_server_usable():
    """A server stuck saying "starting" is a server nobody can use again without a
    restart, which is the thing this whole task is about."""

    def build(cfg, args, herald):
        raise SetupError("no campaign at nowhere/campaign.yaml")

    manager = lifecycle(build=build)
    assert manager.start("nowhere").accepted

    until(lambda: manager.phase == IDLE, "returned to idle")
    assert "no campaign at" in manager.state()["error"]
    assert manager.start("salt-road").accepted, "the server refused to try again"


def test_a_seat_that_falls_over_is_not_a_setup_error_and_still_lands_idle():
    """`SetupError` is the failure this code knows about. A disk that filled or an
    endpoint that hung up is not, and a server that only caught the tidy one would hang
    on the untidy one."""

    def build(cfg, args, herald):
        raise ConnectionError("toto-llm said no")

    manager = lifecycle(build=build)
    manager.start("salt-road")

    until(lambda: manager.phase == IDLE, "returned to idle")
    assert "ConnectionError" in manager.state()["error"]


def test_a_browser_watching_an_idle_server_is_told_when_an_evening_starts():
    """Found by writing this test, and it was a real one.

    Each evening gets its own `Mirror`, so `start` swaps the idle one out — and a
    browser subscribed to the old one would never be pushed anything again. The idle
    mirror is not `ended` by any evening, so that stream would never drop either: the
    person who pressed the button would watch a start screen all night while the evening
    they asked for ran beside them. Ending the outgoing mirror is what makes
    `EventSource` reconnect onto the new one.
    """
    release = threading.Event()
    manager = lifecycle(run=lambda *a, **k: (release.wait(WAIT), Closed(True))[1])
    watching = manager.mirror.subscribe()

    assert manager.start("salt-road").accepted

    until(lambda: watching.queue.qsize() >= 1, "told the idle watcher anything")
    assert "ended" in watching.queue.get_nowait()
    release.set()


def test_the_page_is_told_why_rather_than_left_looking_idle():
    """A failure has to reach the mirror the browser lands on after that reconnect,
    or the only evidence is a `phase` that flickered back to idle."""
    manager = lifecycle(build=lambda *a: (_ for _ in ()).throw(SetupError("nope")))
    manager.start("salt-road")
    until(lambda: manager.phase == IDLE, "returned to idle")

    assert "nope" in manager.state()["error"]


# --- ending ----------------------------------------------------------------


def test_ending_says_quit_on_the_floor_rather_than_reaching_into_the_session():
    """One way to end an evening, so there is one way for the sweep and the chronicle
    to run. A second path would be a second path that skips them."""
    release = threading.Event()
    manager = lifecycle(run=lambda *a, **k: (release.wait(WAIT), Closed(True))[1])
    manager.start("salt-road")
    until(lambda: manager.phase == PLAYING, "reached playing")

    floor = manager.floor
    assert manager.end().accepted
    line = floor.next(timeout=1.0)
    assert line is not None and line.text == "/quit"
    release.set()


def test_ending_nothing_is_refused_with_a_reason():
    refused = lifecycle().end()

    assert refused.accepted is False
    assert refused.reason == "nothing is playing"


# --- what kind of server this is -------------------------------------------


def test_a_hosted_server_can_start_and_can_play():
    manager = lifecycle()

    assert manager.can_manage is True
    assert manager.can_play is True


def test_a_hosted_spectator_server_still_builds_no_write_route():
    """`--watch-only` on the command line is still protection by absence, and P6.7b-iii
    did not quietly trade that away — `can_play` is what `build_app` asks."""
    manager = lifecycle(args=args_for(watch_only=True))

    assert manager.can_play is False


def test_a_held_evening_cannot_be_asked_to_start_another():
    held = Held(Mirror(), Floor())

    assert held.can_manage is False
    assert held.can_play is True
    assert held.phase == PLAYING
    refused = held.start("salt-road")
    assert refused.accepted is False
    assert "already running" in refused.reason


def test_a_held_spectator_link_can_neither_play_nor_manage():
    held = Held(Mirror(), None)

    assert held.can_play is False
    assert held.can_manage is False
    assert held.end().accepted is False


def test_a_held_evening_that_has_ended_reads_as_idle():
    mirror = Mirror()
    held = Held(mirror, Floor())
    mirror.ended()

    assert held.phase == IDLE
    assert held.end().accepted is False


def test_a_held_server_offers_no_campaign_list():
    """A menu with no kitchen behind it. It cannot start one, so it lists none."""
    assert Held(Mirror(), Floor()).campaigns() == []


@pytest.mark.parametrize("phase", [IDLE, STARTING, PLAYING])
def test_every_phase_is_a_string_the_page_can_switch_on(phase):
    assert isinstance(phase, str) and phase.islower()


# --- the routes a browser actually uses -------------------------------------


def client_for(evenings):
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    return TestClient(build_app(evenings), raise_server_exceptions=False)


def test_a_hosted_server_offers_the_routes_a_start_screen_needs():
    manager = lifecycle()
    client = client_for(manager)

    listed = client.get("/api/campaigns")
    assert listed.status_code == 200
    assert "campaigns" in listed.json()

    assert client.post("/api/session", json={"campaign": "salt-road"}).status_code == 202
    until(lambda: manager.phase == IDLE, "finished the evening it was asked for")


def test_starting_twice_over_http_is_a_conflict_and_says_why():
    release = threading.Event()
    manager = lifecycle(run=lambda *a, **k: (release.wait(WAIT), Closed(True))[1])
    client = client_for(manager)

    assert client.post("/api/session", json={"campaign": "salt-road"}).status_code == 202
    until(lambda: manager.phase in (STARTING, PLAYING), "began")

    second = client.post("/api/session", json={"campaign": "ford"})
    assert second.status_code == 409
    assert "already" in second.json()["reason"]
    release.set()


def test_ending_over_http_reaches_the_floor():
    release = threading.Event()
    manager = lifecycle(run=lambda *a, **k: (release.wait(WAIT), Closed(True))[1])
    client = client_for(manager)

    client.post("/api/session", json={"campaign": "salt-road"})
    until(lambda: manager.phase == PLAYING, "reached playing")
    floor = manager.floor

    assert client.post("/api/session/end").status_code == 202
    line = floor.next(timeout=1.0)
    assert line is not None and line.text == "/quit"
    release.set()


def test_ending_nothing_over_http_is_a_conflict():
    refused = client_for(lifecycle()).post("/api/session/end")

    assert refused.status_code == 409
    assert refused.json()["reason"] == "nothing is playing"


def test_a_turn_offered_while_nothing_is_playing_is_refused_not_crashed():
    """The write routes exist on a hosted server even while it is idle, because a route
    table cannot be rebuilt between evenings. They must therefore have an answer for the
    idle case that is not a traceback."""
    refused = client_for(lifecycle()).post(
        "/api/turn", json={"character": "Brannoc", "text": "I wade in"}
    )

    assert refused.status_code == 409
    assert refused.json()["reason"] == "nothing is playing"


def test_the_page_is_told_what_kind_of_server_it_reached():
    hosted = client_for(lifecycle()).get("/api/table").json()
    held = client_for(Held(Mirror(), Floor())).get("/api/table").json()

    assert hosted["manageable"] is True and hosted["phase"] == IDLE
    assert held["manageable"] is False and held["phase"] == PLAYING


def test_a_held_server_has_no_session_routes_at_all():
    """P6.3's shape, kept: not refused, not built. A `dndc play --serve` cannot be asked
    to start a second evening, and the honest way to say so is 404."""
    client = client_for(Held(Mirror(), Floor()))

    assert client.post("/api/session", json={"campaign": "x"}).status_code == 404
    assert client.post("/api/session/end").status_code == 404
    assert client.get("/api/campaigns").status_code == 404


def test_a_hosted_spectator_server_has_no_write_route_either():
    manager = lifecycle(args=args_for(watch_only=True))
    client = client_for(manager)

    assert client.post("/api/turn", json={"text": "x"}).status_code == 404
    # It can still be asked to start one — watching is what the *evening* is, not the
    # server, and the flag is still a property of the command that started it.
    assert client.get("/api/campaigns").status_code == 200


def test_every_new_route_is_behind_the_gate():
    """The route-table walk from `test_gate`, aimed at the routes P6.7b-iii added.

    That test walks a `Held` app and so never sees these. A gate is worth what its least
    protected route is worth, and three new routes arrived after it was written.
    """
    from dndc.web.gate import Gate
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    guarded = TestClient(
        build_app(lifecycle(), Gate("k" * 24)), raise_server_exceptions=False
    )
    checked = 0
    for route in build_app(lifecycle(), Gate("k" * 24)).routes:
        path = getattr(route, "path", None)
        if not path or path.startswith("/openapi") or "session" not in path and "campaigns" not in path:
            continue
        for method in getattr(route, "methods", set()) & {"GET", "POST"}:
            assert guarded.request(method, path, json={}).status_code == 401, path
            checked += 1
    assert checked == 3, f"expected the three new routes, walked {checked}"
