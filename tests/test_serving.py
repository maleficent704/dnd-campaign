"""P6.6: where the table listens, and who that lets in.

The load-bearing assertions here are about a *default*. `web/server.py` used to bind every
interface, on the reasoning that the point of serving is the other sofa — which is true,
and which is not what `0.0.0.0` means on a machine that is also a Tailscale node. The
tests that matter are the ones that fail if the shipped default quietly widens again:
`test_the_shipped_config_does_not_bind_every_interface` and its neighbours.

The rest is the seam being in the right place: the address is config, a flag overrides it
for one evening, and `serve` is `play` with a different front end rather than a second
program.
"""

from __future__ import annotations

import argparse
import json

import pytest
from pydantic import ValidationError

from dndc.config import (
    DEFAULT_WEB_HOST,
    WEB_TOKEN_ENV,
    DEFAULT_WEB_PORT,
    EVERY_INTERFACE,
    LAN,
    Config,
    WebConfig,
    load_config,
)
from dndc.game.floor import WEB, Floor, Refusal
from dndc.gm.context import CampaignContext, PartyMember
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)
from dndc.web.mirror import Mirror
from dndc.web.server import WILDCARD, Server, lan_address, resolve_host
from dndc.web.view import table_view

PARTY = {"Corin Vale", "Brother Hammond"}


def sheet(name: str = "Corin Vale", player: str = "Kelly") -> CharacterSheet:
    return CharacterSheet(
        name=name, player=player, pronouns="she/her", species="Half-Elf",
        character_class="Rogue",
        abilities=AbilityScores(str=8, dex=15, con=13, int=12, wis=10, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=9, current=6), armor_class=14,
    )


def campaign() -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        scene="the Brakewater crossroads",
        party=[
            PartyMember.from_sheet(sheet()),
            PartyMember.from_sheet(sheet("Brother Hammond", player="Sam")),
        ],
    )


# --- the address is config, not a constant ----------------------------------


def test_a_config_written_before_phase_six_still_loads():
    """A table that never serves should not have to say so."""
    web = WebConfig()

    assert web.host == DEFAULT_WEB_HOST
    assert web.port == DEFAULT_WEB_PORT


def test_the_default_is_the_lan_and_not_every_interface():
    assert DEFAULT_WEB_HOST == LAN
    assert DEFAULT_WEB_HOST not in WILDCARD


def test_the_shipped_config_does_not_bind_every_interface():
    """The one that fails if somebody flips the repo's own default back.

    Everything else here tests a mechanism. This tests the setting the family actually
    gets, which is the only version of it anybody runs.
    """
    web = load_config().web

    assert web.host not in WILDCARD
    assert web.host == LAN


def test_an_address_is_taken_as_written():
    assert WebConfig(host="192.168.50.160").host == "192.168.50.160"


def test_surrounding_whitespace_does_not_become_a_hostname():
    assert WebConfig(host="  192.168.50.160 ").host == "192.168.50.160"


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_host_is_refused_with_the_options(bad):
    with pytest.raises(ValidationError) as caught:
        WebConfig(host=bad)

    assert LAN in str(caught.value)


@pytest.mark.parametrize(
    "bad", ["http://192.168.50.160:8765", "https://kelly-pc", "192.168.50.160/"]
)
def test_a_url_pasted_out_of_a_browser_is_refused_here(bad):
    """Rather than deep inside uvicorn, with an error that never says `config.yaml`."""
    with pytest.raises(ValidationError) as caught:
        WebConfig(host=bad)

    assert "not a URL" in str(caught.value)


@pytest.mark.parametrize("bad", [0, -1, 65536, 99999])
def test_a_port_outside_the_range_is_refused(bad):
    with pytest.raises(ValidationError):
        WebConfig(port=bad)


def test_a_typo_in_the_web_block_is_not_silently_ignored():
    """`_Strict` everywhere: a misspelled key that does nothing is worse than an error."""
    with pytest.raises(ValidationError):
        WebConfig(hosts="lan")


def test_the_web_block_is_part_of_the_config_object():
    cfg = load_config()

    assert isinstance(cfg.web, WebConfig)
    assert isinstance(cfg, Config)


# --- `lan` means the address this machine has now ---------------------------


def test_lan_resolves_to_this_machine_rather_than_to_a_literal():
    """Not written into the file: an address there goes stale on the next DHCP lease, and
    a stale bind address does not fail loudly — it binds to nothing and reports success."""
    resolved = resolve_host(LAN)

    assert resolved != LAN
    assert resolved == lan_address()


def test_lan_is_matched_however_it_was_typed():
    assert resolve_host("LAN") == lan_address()
    assert resolve_host(" Lan ") == lan_address()


def test_anything_else_is_taken_at_its_word():
    assert resolve_host("127.0.0.1") == "127.0.0.1"
    assert resolve_host(EVERY_INTERFACE) == EVERY_INTERFACE
    assert resolve_host(" 192.168.50.46 ") == "192.168.50.46"


def test_lan_address_is_a_real_address_and_not_a_hostname():
    parts = lan_address().split(".")

    assert len(parts) == 4
    assert all(part.isdigit() for part in parts)


# --- what the server says it is ---------------------------------------------


def server(host: str) -> Server:
    return Server(Mirror(), host=host, port=8765)


def test_the_server_keeps_what_was_asked_for_and_what_it_resolved_to():
    """So a message can say what the table chose, not only where the socket landed."""
    running = server(LAN)

    assert running.requested == LAN
    assert running.host == lan_address()


@pytest.mark.parametrize("host", [EVERY_INTERFACE, "::", "*"])
def test_a_wildcard_bind_knows_it_is_one(host):
    assert server(host).everywhere is True


@pytest.mark.parametrize("host", [LAN, "127.0.0.1", "192.168.50.46"])
def test_a_narrow_bind_is_not_mistaken_for_a_wildcard(host):
    assert server(host).everywhere is False


def test_the_address_read_out_loud_is_never_the_wildcard():
    assert EVERY_INTERFACE not in server(EVERY_INTERFACE).url
    assert server(EVERY_INTERFACE).url == f"http://{lan_address()}:8765"


def test_a_narrow_bind_is_read_out_as_itself():
    assert server("127.0.0.1").url == "http://127.0.0.1:8765"
    assert server(LAN).url == f"http://{lan_address()}:8765"


# --- the flag overrides the file, for one evening ---------------------------


class Recorded:
    """A stand-in for `Server` that records the address it was asked for."""

    seen: list[tuple[str, int]] = []

    def __init__(self, mirror, host, port, floor=None, gate=None):
        Recorded.seen.append((host, port))
        self.host, self.port, self.floor = host, port, floor
        self.gate = gate
        self.everywhere = host in WILDCARD
        self.guarded = gate is not None and gate.guarded
        self.url = f"http://{host}:{port}"

    def start(self) -> None:
        pass


@pytest.fixture
def recording(monkeypatch):
    from dndc.game import cli

    Recorded.seen = []
    monkeypatch.setattr(cli, "Server", Recorded)
    return Recorded


def start_mirror(recording, host=None, port=None, floor=None):
    from rich.console import Console

    from dndc.game import cli

    console = Console(record=True, width=100)
    args = argparse.Namespace(serve_host=host, serve_port=port, require_token=False)
    server = cli._start_mirror(console, load_config(), Mirror(), args, floor)
    return server, console.export_text()


def test_with_no_flags_the_address_comes_out_of_the_file(recording):
    start_mirror(recording)
    cfg = load_config()

    assert recording.seen == [(cfg.web.host, cfg.web.port)]


def test_a_flag_overrides_the_file_without_changing_it(recording):
    start_mirror(recording, host="127.0.0.1", port=9999)

    assert recording.seen == [("127.0.0.1", 9999)]
    assert load_config().web.host == LAN  # the file is untouched


def test_one_flag_overrides_one_thing(recording):
    """Half an override is a real case: a different port on the usual interface."""
    start_mirror(recording, port=9999)
    cfg = load_config()

    assert recording.seen == [(cfg.web.host, 9999)]


def test_binding_every_interface_without_a_key_refuses_to_serve(recording, monkeypatch):
    """Changed by P6.7b, deliberately. P6.6 warned and played on; that was right while the
    only exposure was an evening somebody started in the room, and it stopped being right
    the moment the same flag could reach a phone on cellular. A wildcard bind is now one of
    the two exposures that make the token mandatory."""
    monkeypatch.delenv(WEB_TOKEN_ENV, raising=False)
    server, printed = start_mirror(recording, host=EVERY_INTERFACE)

    assert server is None
    assert "refusing to serve" in printed
    assert WEB_TOKEN_ENV in printed
    assert recording.seen == []  # it never got as far as a socket


def test_binding_every_interface_says_so_out_loud(recording, monkeypatch):
    monkeypatch.setenv(WEB_TOKEN_ENV, "k" * 24)
    _, printed = start_mirror(recording, host=EVERY_INTERFACE)

    assert "every interface" in printed
    assert "tailnet" in printed
    # The token is not authentication and the widest bind is where saying so matters most.
    assert "not a login" in printed


def test_the_usual_case_is_not_shouted_at(recording):
    _, printed = start_mirror(recording)

    assert "tailnet" not in printed
    assert "from the sofa" in printed


def test_a_spectator_link_says_it_is_read_only(recording):
    _, printed = start_mirror(recording, floor=None)

    assert "read-only" in printed


def test_a_playable_link_says_so(recording):
    _, printed = start_mirror(recording, floor=Floor())

    assert "playing from it" in printed


def test_a_mirror_that_will_not_start_is_not_fatal(monkeypatch):
    """The port is taken, or the extra is missing. Neither is a reason nobody plays."""
    from rich.console import Console

    from dndc.game import cli

    class Refuses(Recorded):
        def start(self):
            raise OSError("address already in use")

    monkeypatch.setattr(cli, "Server", Refuses)
    console = Console(record=True, width=100)
    args = argparse.Namespace(serve_host=None, serve_port=None, require_token=False)

    assert cli._start_mirror(console, load_config(), Mirror(), args, None) is None
    assert "did not start" in console.export_text()


# --- `serve` is `play` with a different front end ---------------------------


def parser():
    from dndc.game.cli import build_parser

    return build_parser()


def test_serve_takes_the_same_options_as_play():
    """One list, in one place. Two copies would drift inside a single task."""
    play = vars(parser().parse_args(["play", "--campaign", "x"]))
    serve = vars(parser().parse_args(["serve", "--campaign", "x"]))

    assert set(play) - set(serve) == {"serve"}
    assert set(serve) - set(play) == set()


def test_play_still_has_to_be_asked_to_serve():
    assert parser().parse_args(["play", "--campaign", "x"]).serve is False
    assert parser().parse_args(["play", "--campaign", "x", "--serve"]).serve is True


def test_serve_does_not_take_a_serve_flag():
    """It would be the only flag on the command that could not be false."""
    with pytest.raises(SystemExit):
        parser().parse_args(["serve", "--campaign", "x", "--serve"])


def test_the_address_flags_default_to_deferring_to_config():
    for command in ("play", "serve"):
        args = parser().parse_args([command, "--campaign", "x"])

        assert args.serve_host is None
        assert args.serve_port is None


def test_serve_is_the_same_loop_and_not_a_second_one(monkeypatch):
    from dndc.game import cli

    captured = {}
    monkeypatch.setattr(cli, "_cmd_play", lambda console, args: captured.setdefault("args", args))
    args = parser().parse_args(["serve", "--campaign", "x"])
    cli._cmd_serve(None, args)

    assert captured["args"] is args
    assert args.serve is True


def test_serve_asks_nothing_at_a_console_that_may_not_exist(monkeypatch):
    """D-004's sticky default still applies; `--billing` still overrides it."""
    from dndc.game import cli

    monkeypatch.setattr(cli, "_cmd_play", lambda console, args: 0)
    args = parser().parse_args(["serve", "--campaign", "x"])
    cli._cmd_serve(None, args)

    assert args.no_prompt is True


def test_serve_can_still_be_a_spectator_link():
    assert parser().parse_args(["serve", "--campaign", "x", "--watch-only"]).watch_only is True


# --- two devices ------------------------------------------------------------


def test_two_devices_both_see_the_same_turn():
    """P6.6's point: not one screen, two. Each gets its own queue."""
    mirror = Mirror()
    kelly, sam = mirror.subscribe(), mirror.subscribe()
    mirror.show(table_view(campaign(), acting="Corin Vale"))

    assert mirror.watching == 2
    for device in (kelly, sam):
        assert json.loads(device.queue.get_nowait())["kind"] == "table"


def test_one_device_leaving_does_not_take_the_other_with_it():
    mirror = Mirror()
    kelly, sam = mirror.subscribe(), mirror.subscribe()
    mirror.unsubscribe(sam)
    mirror.show(table_view(campaign(), acting="Corin Vale"))

    assert mirror.watching == 1
    assert not kelly.queue.empty()


def test_only_the_acting_player_may_speak_from_their_device():
    """Sam's phone waits while it is Kelly's turn — the same rule the keyboard has."""
    floor = Floor()

    assert floor.offer("Corin Vale", "I try the door.", "Corin Vale", PARTY).accepted
    assert not floor.offer("Brother Hammond", "I follow.", "Corin Vale", PARTY).accepted


def test_the_refusal_says_which_kind_it_is():
    floor = Floor()
    refused = floor.offer("Brother Hammond", "I follow.", "Corin Vale", PARTY)

    assert refused.refusal is Refusal.NOT_YOUR_TURN
    assert refused.reason == "it is not your turn"


def test_the_turn_passes_and_so_does_the_device_that_may_speak():
    floor = Floor()
    floor.offer("Corin Vale", "I try the door.", "Corin Vale", PARTY)
    floor.next(timeout=1)

    assert floor.offer("Brother Hammond", "I follow.", "Brother Hammond", PARTY).accepted


def test_a_line_from_a_device_is_marked_as_one():
    """So the terminal can say who spoke and from where, with two people in two rooms."""
    floor = Floor()
    floor.offer("Brother Hammond", "I bar the door.", "Brother Hammond", PARTY)
    line = floor.next(timeout=1)

    assert line.source == WEB
    assert line.character == "Brother Hammond"


# --- two devices, over a real socket ----------------------------------------

fastapi = pytest.importorskip("fastapi", reason="the `web` extra is optional")


@pytest.fixture
def table():
    from fastapi.testclient import TestClient

    from dndc.web.app import build_app

    mirror, floor = Mirror(), Floor()
    mirror.show(table_view(campaign(), acting="Corin Vale"))
    app = build_app(mirror, floor)
    return TestClient(app), TestClient(app), floor


def test_both_devices_are_served_the_same_table(table):
    kelly, sam, _ = table

    assert kelly.get("/api/table").json() == sam.get("/api/table").json()


def test_a_turn_from_one_device_is_refused_from_the_other(table):
    kelly, sam, _ = table
    mine = kelly.post("/api/turn", json={"character": "Corin Vale", "text": "I try the door."})
    theirs = sam.post("/api/turn", json={"character": "Brother Hammond", "text": "I follow."})

    assert mine.status_code == 202
    assert theirs.status_code == 409
    assert theirs.json()["refusal"] == Refusal.NOT_YOUR_TURN.value


def test_the_second_device_is_told_why_rather_than_ignored(table):
    """A phone that silently does nothing is indistinguishable from a broken phone."""
    _, sam, _ = table
    refused = sam.post("/api/turn", json={"character": "Brother Hammond", "text": "I follow."})

    assert refused.json()["reason"] == "it is not your turn"
    assert refused.json()["accepted"] is False
