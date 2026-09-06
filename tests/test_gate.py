"""P6.7b: the LAN gate — one shared token, and the routes it actually covers.

Kelly ruled the shape on 2026-09-04: a fixed token in `.env`, matching `the-room`'s
`ROOM_TOKEN`, not the per-session code `docs/LAN-ACCESS.md` used to recommend.

Two tests here carry more weight than the rest.

`test_no_route_on_a_guarded_app_answers_an_anonymous_request` walks the app's own route
table rather than a list written by hand, so a route added in P6.7b-iii or P6.7c that
forgets the gate fails this file instead of shipping. A gate is only worth what its
*least* protected route is worth, and a hand-maintained list of routes to check is a list
somebody eventually forgets to add to.

`test_the_event_stream_is_gated` is the one the design turns on. A browser cannot put an
`Authorization` header on an `EventSource`, so the obvious implementation gates the write
routes and leaves the stream open — which would be a gate on the door of a room with no
wall, since the narration is what flows down the stream. The cookie exists for this.

The other thing pinned here is the *un*gated case. An evening on the LAN, started by
somebody in the room, is still open, and it has to stay that way: forcing a token on
`dndc play --serve` would break the evening Kelly and Sam actually play in exchange for
nothing, which is why `resolve_gate` takes `required` rather than deciding for itself.
"""

from __future__ import annotations

import pytest

from dndc.config import MIN_WEB_TOKEN, WEB_REQUIRE_TOKEN_ENV, WEB_TOKEN_ENV
from dndc.game.floor import Floor
from dndc.web.gate import (
    COOKIE,
    QUERY,
    Gate,
    TokenError,
    configured_token,
    deployment_requires,
    first_offered,
    resolve_gate,
    token_from_header,
)
from dndc.web.lifecycle import Held
from dndc.web.mirror import Mirror
from dndc.web.view import table_view

from test_mirror import campaign

GOOD = "a-long-enough-token-to-be-real"


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    monkeypatch.delenv(WEB_TOKEN_ENV, raising=False)
    monkeypatch.delenv(WEB_REQUIRE_TOKEN_ENV, raising=False)


# --- where the token comes from ----------------------------------------------------


def test_the_token_comes_from_the_environment_and_nowhere_else(monkeypatch):
    assert configured_token() is None
    monkeypatch.setenv(WEB_TOKEN_ENV, GOOD)
    assert configured_token() == GOOD


def test_a_blank_token_is_no_token(monkeypatch):
    """`DNDC_WEB_TOKEN=` in a .env is somebody meaning to turn it off, not a token."""
    monkeypatch.setenv(WEB_TOKEN_ENV, "   ")
    assert configured_token() is None


@pytest.mark.parametrize("value", ["", "0", "false", "no", "  "])
def test_the_deployment_switch_is_off_by_these(monkeypatch, value):
    monkeypatch.setenv(WEB_REQUIRE_TOKEN_ENV, value)
    assert deployment_requires() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "please"])
def test_the_deployment_switch_is_on_by_anything_else(monkeypatch, value):
    monkeypatch.setenv(WEB_REQUIRE_TOKEN_ENV, value)
    assert deployment_requires() is True


# --- required means refused, not degraded ------------------------------------------


def test_an_evening_on_the_lan_may_be_open():
    """The posture P6.6 documented and this house uses for every LAN service."""
    gate = resolve_gate(required=False)

    assert gate.guarded is False
    assert gate.admits() is True


def test_a_required_gate_with_no_token_refuses_to_be_built():
    with pytest.raises(TokenError, match=WEB_TOKEN_ENV):
        resolve_gate(required=True)


def test_a_required_gate_refuses_a_token_short_enough_to_guess(monkeypatch):
    monkeypatch.setenv(WEB_TOKEN_ENV, "hunter2")
    with pytest.raises(TokenError, match=str(MIN_WEB_TOKEN)):
        resolve_gate(required=True)


def test_a_required_gate_with_a_real_token_is_guarded(monkeypatch):
    monkeypatch.setenv(WEB_TOKEN_ENV, GOOD)
    assert resolve_gate(required=True).guarded is True


# --- how a token may arrive --------------------------------------------------------


@pytest.mark.parametrize(
    "header,expected",
    [
        (f"Bearer {GOOD}", GOOD),
        (f"bearer {GOOD}", GOOD),
        (GOOD, GOOD),
        # A scheme with nothing after it is not a scheme; it falls through to the bare
        # form and is treated as the token "Bearer", which will not match a real one.
        ("Bearer   ", "Bearer"),
        ("", None),
        (None, None),
    ],
)
def test_a_bearer_scheme_is_tolerated_but_not_required(header, expected):
    assert token_from_header(header) == expected


def test_the_most_explicit_carrier_wins():
    """A stale cookie in a browser must not override the token a script meant to send."""
    assert first_offered(header="one", cookie="two", query="three") == "one"
    assert first_offered(cookie="two", query="three") == "two"
    assert first_offered(query="three") == "three"
    assert first_offered() is None


def test_an_open_gate_admits_everything():
    assert Gate(None).admits() is True
    assert Gate(None).admits(header="nonsense") is True


@pytest.mark.parametrize("carrier", ["header", "cookie", "query"])
def test_a_guarded_gate_admits_the_token_however_it_arrives(carrier):
    assert Gate(GOOD).admits(**{carrier: GOOD}) is True


def test_a_guarded_gate_refuses_nothing_and_refuses_wrong():
    gate = Gate(GOOD)

    assert gate.admits() is False
    assert gate.admits(header=GOOD + "x") is False
    assert gate.admits(cookie="") is False


# --- the HTTP surface ---------------------------------------------------------------

fastapi = pytest.importorskip("fastapi", reason="the `web` extra is optional")


def build(gate, floor=None, ended=False):
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    mirror = Mirror()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    if ended:
        # The stream only terminates when the evening does, so a test that reads one to
        # the end has to end it first. Same reason `test_mirror.frames` does it.
        mirror.ended()
    return TestClient(build_app(Held(mirror, floor), gate))


@pytest.fixture
def guarded():
    return build(Gate(GOOD), floor=Floor())


@pytest.fixture
def open_table():
    return build(Gate(None), floor=Floor())


def test_no_route_on_a_guarded_app_answers_an_anonymous_request(guarded):
    """Walked off the app's own routes, so a new one cannot quietly arrive ungated.

    A gate is worth what its least protected route is worth, and a hand-written list of
    routes to check is a list somebody forgets to add to.
    """
    from dndc.web.app import build_app

    app = build_app(Held(Mirror(), Floor()), Gate(GOOD))
    checked = 0  # every request below is anonymous, so no stream is ever opened
    for route in app.routes:
        path, methods = getattr(route, "path", None), getattr(route, "methods", set())
        if not path or path.startswith("/openapi"):
            continue
        for method in methods & {"GET", "POST"}:
            response = guarded.request(method, path, json={})
            assert response.status_code == 401, f"{method} {path} answered anonymously"
            checked += 1
    assert checked >= 5, f"only {checked} routes checked — the walk found too few"


def test_the_event_stream_is_gated():
    """The route the cookie exists for: the narration flows here."""
    client = build(Gate(GOOD), floor=Floor(), ended=True)

    assert client.get("/api/events").status_code == 401

    admitted = client.get("/api/events", params={QUERY: GOOD})
    assert admitted.status_code == 200
    assert "The Salt Road" in admitted.text


def test_the_page_turns_a_link_into_a_cookie():
    """The bookmark Kelly asked for: `?k=…` once, and the stream works thereafter."""
    guarded = build(Gate(GOOD), floor=Floor(), ended=True)
    refused = guarded.get("/")
    assert refused.status_code == 401
    assert "table is closed" in refused.text.lower()

    admitted = guarded.get("/", params={QUERY: GOOD})
    assert admitted.status_code == 200
    assert "<script" in admitted.text

    biscuit = admitted.cookies.get(COOKIE)
    assert biscuit == GOOD
    assert "httponly" in admitted.headers["set-cookie"].lower()

    # The client keeps the cookie, so the stream now opens without the query string.
    assert guarded.get("/api/events").status_code == 200


def test_an_open_table_hands_out_no_cookie(open_table):
    """Nothing to remember when there is nothing to check."""
    response = open_table.get("/", params={QUERY: "anything"})

    assert response.status_code == 200
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_the_gate_is_checked_before_the_floor_is(guarded):
    """A stranger is told 401, not 409.

    Answering "it is not your turn" to a device that should not be here at all leaks that
    a session exists and whose turn it is, and invites a retry rather than a stop.
    """
    anonymous = guarded.post("/api/turn", json={"character": "Corin Vale", "text": "hi"})

    assert anonymous.status_code == 401
    assert "reason" not in anonymous.json()


def test_a_missing_token_and_a_wrong_one_are_answered_identically(guarded):
    missing = guarded.get("/api/table")
    wrong = guarded.get("/api/table", headers={"Authorization": f"Bearer {GOOD}x"})

    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()


def test_a_header_gets_in_the_way_a_script_would(guarded):
    response = guarded.get("/api/table", headers={"Authorization": f"Bearer {GOOD}"})

    assert response.status_code == 200
    assert response.json()["table"]["campaign"] == "The Salt Road"


def test_an_open_table_still_plays_exactly_as_it_did(open_table):
    """The evening on the LAN is unchanged by this task, which is the point."""
    assert open_table.get("/").status_code == 200
    assert open_table.get("/api/table").status_code == 200

    accepted = open_table.post(
        "/api/turn", json={"character": "Corin Vale", "text": "She steps into the yard."}
    )
    assert accepted.status_code == 202


def test_a_spectator_link_is_still_missing_its_write_route_rather_than_refusing_it():
    """P6.4's shape survives the gate: `--watch-only` builds no `POST`, gated or not."""
    watching = build(Gate(GOOD), floor=None)

    # 404, not 405 and not 401: the route was never registered, so there is nothing to
    # be allowed or refused. A device cannot tell "not permitted" from "does not exist".
    assert watching.post("/api/turn", json={}, params={QUERY: GOOD}).status_code == 404
