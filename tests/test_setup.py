"""P6.7b-ii: building an evening with nobody standing at a terminal.

These are the tests `_cmd_play` could not have. Its hundred and twenty lines of setup
were reachable only through a `rich.Console` and only from `main(["play", ...])`, so
what little covered them covered them by driving the whole command with a scripted
`Prompt` — which is a fine way to test a play loop and a poor way to test construction.

The claim under test is narrow and load-bearing for P6.7b-iii: **an evening can be
built by something that is not a terminal, and it is the same evening.**
"""

from __future__ import annotations

import argparse

import pytest

from dndc.config import Billing, load_config
from dndc.game import campaign as campaign_module
from dndc.game.campaign import campaign_dir, create_campaign
from dndc.game.setup import (
    QuietHerald,
    SetupError,
    build_evening,
    load_party,
    load_sheet,
    resolve_billing,
)
from dndc.models.mock import MockBackend
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)

SLUG = "ford-crossing"


def _sheet(name: str = "Brannoc") -> CharacterSheet:
    return CharacterSheet(
        name=name,
        player="Kelly",
        species="Human",
        character_class="Fighter",
        level=2,
        abilities=AbilityScores(str=16, dex=12, con=14, int=10, wis=11, cha=8),
        proficiencies=Proficiencies(saving_throws=["str", "con"]),
        hit_points=HitPoints(maximum=20, current=13),
        armor_class=16,
    )


@pytest.fixture
def campaign_on_disk(tmp_path, monkeypatch):
    """A real campaign directory, logs under tmp, and no seat that touches anything."""
    monkeypatch.setattr(
        campaign_module, "default_campaigns_root", lambda: tmp_path / "campaigns"
    )
    monkeypatch.setattr(
        "dndc.game.setup.resolve_log_dir", lambda _: tmp_path / "logs"
    )
    create_campaign("Ford Crossing", players=["Kelly"], scaffolding="off")
    _sheet().save(campaign_dir(SLUG) / "characters" / "brannoc.yaml")
    return campaign_dir(SLUG)


def args_for(**overrides) -> argparse.Namespace:
    """The flags `build_evening` reads, at the values `dndc play` gives them."""
    settled = dict(
        campaign=SLUG,
        campaign_name=None,
        scene=None,
        canon=None,
        character=(),
        fresh=False,
        # `None` and `--no-prompt` together mean "the sticky default", which is what
        # `dndc play` does unless somebody passes `--billing`. Naming a value here
        # would make the comparison test below agree with itself by construction.
        billing=None,
        no_prompt=True,
        threshold=None,
        seed=7,
        no_recap=True,
        no_npcs=True,
        gate_seat="utility_batch",
        ungated=False,
        scaffolding="off",
        max_tokens=None,
    )
    settled.update(overrides)
    return argparse.Namespace(**settled)


@pytest.fixture
def gm(monkeypatch) -> MockBackend:
    backend = MockBackend(["The ford is running high."])
    monkeypatch.setattr("dndc.game.setup.build_gm_backend", lambda *a, **k: backend)
    return backend


# --- the whole point -------------------------------------------------------


def test_an_evening_is_built_without_a_console_anywhere(campaign_on_disk, gm):
    """The claim P6.7b-iii rests on. No `Console`, no stdin, no terminal."""
    evening = build_evening(load_config(), args_for(), QuietHerald())

    assert evening.campaign.name == "Ford Crossing"
    assert [member.name for member in evening.campaign.party] == ["Brannoc"]
    assert evening.session.acting == "Brannoc"
    assert evening.seed == 7
    assert evening.backend is gm
    assert evening.log.path.exists()
    evening.session.close()


def test_nothing_has_been_narrated_yet(campaign_on_disk, gm):
    """Construction stops one step short of the first turn, deliberately.

    `open_scene` is the caller's to make: a browser decides when an evening starts,
    and a built-but-unopened session is what lets it. If this ever narrates during
    construction, a page that merely *prepares* an evening has spent money.
    """
    evening = build_evening(load_config(), args_for(), QuietHerald())

    assert gm.calls == []
    assert evening.campaign.history == []
    evening.session.close()


def test_the_module_never_reaches_for_a_terminal(campaign_on_disk):
    """A structural guard, in the shape of `test_gate`'s route walk.

    Console-free is not a thing you can assert by playing an evening — it is a thing
    about the source. A later change that reaches for `rich` inside construction would
    pass every behavioural test in this file and quietly put the terminal back in the
    middle of the thing P6.7b-ii took it out of.
    """
    import ast
    import inspect

    import dndc.game.setup as setup

    tree = ast.parse(inspect.getsource(setup))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "rich" not in imported, "game/setup.py reached for a terminal again"


# --- the failures ----------------------------------------------------------


def test_a_campaign_that_is_not_there_is_a_setup_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        campaign_module, "default_campaigns_root", lambda: tmp_path / "campaigns"
    )
    with pytest.raises(SetupError) as raised:
        load_party(args_for(campaign="no-such-campaign"))

    assert "[red]error:[/red]" in raised.value.markup
    assert "[red]" not in str(raised.value)


def test_a_party_of_nobody_says_what_to_do_about_it(tmp_path, monkeypatch):
    """And says it in yellow, because it is a thing to fix rather than a failure."""
    monkeypatch.setattr(
        campaign_module, "default_campaigns_root", lambda: tmp_path / "campaigns"
    )
    create_campaign("Empty", players=["Kelly"], scaffolding="off")

    with pytest.raises(SetupError) as raised:
        build_evening(load_config(), args_for(campaign="empty"), QuietHerald())

    assert raised.value.markup.startswith("[yellow]no characters loaded[/yellow]")
    assert "--campaign SLUG" in str(raised.value)


def test_a_missing_sheet_names_the_path_it_looked_at(tmp_path):
    with pytest.raises(SetupError) as raised:
        load_sheet(str(tmp_path / "nobody.yaml"))

    assert raised.value.markup == f"[red]error:[/red] no sheet at {tmp_path / 'nobody.yaml'}"


def test_an_unreadable_sheet_is_not_the_same_failure_as_an_invalid_one(tmp_path):
    """Two different sentences, because they are two different things to fix."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("name: [unclosed\n", encoding="utf-8")
    with pytest.raises(SetupError) as unreadable:
        load_sheet(str(broken))

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("name: Brannoc\n", encoding="utf-8")
    with pytest.raises(SetupError) as wrong:
        load_sheet(str(invalid))

    assert "could not read" in unreadable.value.markup
    assert "invalid sheet" in wrong.value.markup
    # The per-field lines survive the move from five prints to one exception.
    assert "\n  - " in wrong.value.markup


def test_a_sheet_that_is_fine_comes_back(tmp_path):
    path = tmp_path / "brannoc.yaml"
    _sheet().save(path)
    assert load_sheet(str(path)).name == "Brannoc"


# --- the herald ------------------------------------------------------------


def test_a_quiet_herald_keeps_what_it_was_told():
    """Not decoration: the recap's "Previously on…" and the NPC seat's warnings are
    the lines P6.7b-iii will most want on a page, and a construction path that has
    already dropped them cannot be asked for them later."""
    herald = QuietHerald()
    herald.say("[dim]previously — reading the campaign back[/dim]")
    with herald.working("[dim]warming the NPC seat…[/dim]"):
        pass

    assert herald.said == [
        "[dim]previously — reading the campaign back[/dim]",
        "[dim]warming the NPC seat…[/dim]",
    ]
    assert herald.can_ask is False
    assert herald.ask("open here?") is None


def test_billing_falls_back_to_the_sticky_default_when_nobody_can_be_asked():
    """What `sys.stdin.isatty()` used to decide inside `resolve_billing`, decided by
    whoever is listening instead — which is the only place that can know."""
    cfg = load_config()
    choice = resolve_billing(cfg, QuietHerald(), requested=None, ask=True, remember=False)
    assert choice is cfg.billing.default


def test_billing_takes_the_answer_when_somebody_is_there():
    class Answering(QuietHerald):
        @property
        def can_ask(self) -> bool:
            return True

        def ask(self, prompt, default="", choices=None):
            return Billing.SUBSCRIPTION.value

    herald = Answering()
    choice = resolve_billing(load_config(), herald, requested=None, ask=True, remember=False)

    assert choice is Billing.SUBSCRIPTION
    # The throttle warning is not optional, and it must reach a browser too.
    assert any("heads-up" in line for line in herald.said)


def test_walking_away_mid_question_is_the_same_as_not_being_asked():
    """`can_ask` said somebody was there and then they left (^D, ^C, a closed tab).
    The sticky default is the right answer for both, and it used to be reached by two
    different routes."""

    class Leaves(QuietHerald):
        @property
        def can_ask(self) -> bool:
            return True

        def ask(self, prompt, default="", choices=None):
            return None

    cfg = load_config()
    choice = resolve_billing(cfg, Leaves(), requested=None, ask=True, remember=False)
    assert choice is cfg.billing.default


def test_the_console_herald_turns_a_walk_away_into_no_answer():
    """The CLI's half of the same contract. `Prompt.ask` raises; `Herald.ask` returns
    `None`, so no caller has to know which of the two silences it got."""
    from rich.console import Console

    from dndc.game.cli import ConsoleHerald

    class Gone:
        @staticmethod
        def ask(*args, **kwargs):
            raise EOFError

    import dndc.game.cli as cli

    original, cli.Prompt = cli.Prompt, Gone
    try:
        assert ConsoleHerald(Console()).ask("anything?") is None
    finally:
        cli.Prompt = original


# --- one way to build one --------------------------------------------------


def test_the_command_and_a_caller_with_no_terminal_build_the_same_evening(
    campaign_on_disk, gm, monkeypatch
):
    """P6.1's rule, applied to construction: one loop because two would drift — and
    the same is true of two ways to *build* one. `dndc play` goes through this
    function, so there is no second path to drift from."""
    import dndc.game.cli as cli

    seen = {}
    real = cli.build_evening
    monkeypatch.setattr(
        cli, "build_evening", lambda cfg, args, herald: seen.setdefault(
            "evening", real(cfg, args, herald)
        )
    )

    class Feed:
        @staticmethod
        def ask(*args, **kwargs):
            raise EOFError

    monkeypatch.setattr(cli, "Prompt", Feed)
    assert cli.main([
        "play", "--campaign", SLUG, "--no-prompt", "--no-npcs", "--no-recap",
        "--no-sweep", "--no-chronicle", "--scaffolding", "off", "--seed", "7",
    ]) == 0

    from_the_command = seen["evening"]
    headless = build_evening(load_config(), args_for(), QuietHerald())
    try:
        assert from_the_command.campaign.name == headless.campaign.name
        assert from_the_command.session.acting == headless.session.acting
        assert from_the_command.seed == headless.seed
        assert from_the_command.billing is headless.billing
    finally:
        headless.session.close()


def test_the_thrashing_warning_still_has_somebody_to_warn():
    """It used to make its own `Console()` — the one place in setup that did.

    Which meant it was the one line here with no caller-visible seam, and the only
    reason the suite has never run it: the warning needs a gate seat on the NPC seat's
    endpoint running a different model, which no test config sets up. A warning nothing
    exercises is a warning that can quietly stop working, so this exercises it.
    """
    from dndc.game.setup import _warn_if_thrashing

    cfg = load_config()

    class Seat:
        endpoint = cfg.seats.npc.endpoint
        model = cfg.seats.npc.model + "-but-smaller"

    herald = QuietHerald()
    _warn_if_thrashing(cfg, Seat(), herald)

    assert len(herald.said) == 1
    assert "[yellow]warning:[/yellow]" in herald.said[0]
    assert Seat.model in herald.said[0] and cfg.seats.npc.model in herald.said[0]


def test_a_gate_seat_that_matches_the_npc_seat_is_not_warned_about():
    from dndc.game.setup import _warn_if_thrashing

    cfg = load_config()

    class Same:
        endpoint = cfg.seats.npc.endpoint
        model = cfg.seats.npc.model

    herald = QuietHerald()
    _warn_if_thrashing(cfg, Same(), herald)
    assert herald.said == []
