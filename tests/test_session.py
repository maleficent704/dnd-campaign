"""P6.1: one turn loop, two front ends.

The load-bearing assertion in this file is that a session runs to completion against a
table that is not a terminal. Everything Phase 6 puts in a browser depends on that being
true, and on it staying true — a loop that quietly grows a `rich` dependency is a loop the
web has to fork, and a forked loop is two campaigns.
"""

from __future__ import annotations

import random

import pytest

from dndc.game.saves import SaveStore
from dndc.game.session import (
    PlaySession,
    SessionError,
    Table,
    acting_member,
    build_engine,
    draw_seed,
    resume_from,
)
from dndc.game.turn import TurnEngine
from dndc.gm.context import CampaignContext, PartyMember
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
)


def sheet(name: str = "Brannoc", player: str = "Kelly") -> CharacterSheet:
    return CharacterSheet(
        name=name,
        player=player,
        species="Human",
        character_class="Fighter",
        level=2,
        abilities=AbilityScores(str=16, dex=12, con=14, int=10, wis=11, cha=8),
        proficiencies=Proficiencies(saving_throws=["str", "con"]),
        hit_points=HitPoints(maximum=20, current=13),
        armor_class=16,
    )


class Paper:
    """A table made of a list. No console, no rich, no terminal of any kind.

    This is the whole point of the task: if `PlaySession` can be driven by this, it can be
    driven by an HTTP handler, and the browser and the terminal are playing one campaign.
    """

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.text = ""
        self.dialogue_lines: list = []
        self.applied = 0

    # --- Table ---------------------------------------------------------
    def notice(self, text: str) -> None:
        self.events.append(("notice", text))

    def error(self, text: str) -> None:
        self.events.append(("error", text))

    def narration(self):
        return self

    def opened(self, result) -> None:
        self.events.append(("opened", result.narration))

    def played(self, result) -> None:
        self.events.append(("played", result.narration))

    def inventory(self, tags, acting: str, turn: int) -> int:
        self.events.append(("inventory", acting, len(tuple(tags))))
        return self.applied

    def sweep(self, session) -> None:
        self.events.append(("sweep",))

    def chronicle(self, session) -> None:
        self.events.append(("chronicle",))

    # --- Narration -----------------------------------------------------
    def feed(self, chunk: str) -> None:
        self.text += chunk

    def dialogue(self, reply) -> None:
        self.dialogue_lines.append(reply)

    def finish(self) -> None:
        self.events.append(("finished",))

    # --- helpers -------------------------------------------------------
    def kinds(self) -> list[str]:
        return [event[0] for event in self.events]


class _Closer:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def session(
    backend: MockBackend | None = None,
    *,
    saves: SaveStore | None = None,
    closers=(),
    party=("Brannoc",),
    scene: str = "a ford",
) -> PlaySession:
    sheets = {name.lower(): sheet(name) for name in party}
    campaign = CampaignContext(
        name="Ford Crossing",
        scene=scene,
        party=[PartyMember.from_sheet(one) for one in sheets.values()],
    )
    backend = backend or MockBackend(["The ford is loud tonight."])
    engine = TurnEngine(backend=backend, campaign=campaign, rng=random.Random(1))
    return PlaySession.start(
        campaign,
        sheets,
        backend=backend,
        log=None,
        engine=engine,
        items=None,
        acting=acting_member(campaign, None),
        billing="api",
        seed=1,
        saves=saves,
        closers=closers,
    )


# --- a session with no terminal --------------------------------------------


def test_a_whole_session_runs_against_a_table_made_of_a_list():
    table = Paper()
    subject = session()

    subject.open_scene(table)
    subject.take_turn("I wade in", table)
    subject.finish(table)
    subject.close()

    assert subject.campaign.history
    assert table.text
    assert "opened" in table.kinds() and "played" in table.kinds()


def test_the_console_front_end_is_a_conforming_table():
    """Pinned so the protocol and the CLI cannot drift apart silently. If a later task
    adds a method here, the terminal has to answer it too — which is the point: a front
    end may render a question however it likes and may not decline to be asked."""
    from dndc.game.cli import ConsoleTable

    assert isinstance(ConsoleTable(None, None, None, None), Table)


def test_a_session_with_nobody_in_it_will_not_start():
    campaign = CampaignContext(name="Empty")
    with pytest.raises(SessionError, match="no characters"):
        PlaySession.start(
            campaign, {}, backend=MockBackend(), log=None,
            engine=TurnEngine(backend=MockBackend(), campaign=campaign),
            items=None, acting="", billing="api", seed=1,
        )


# --- the opening scene -----------------------------------------------------


def test_the_gm_speaks_first():
    table = Paper()
    subject = session()

    subject.open_scene(table)

    assert table.text == "The ford is loud tonight."
    assert len(subject.campaign.history) == 1


def test_a_session_walking_back_into_a_running_scene_does_not_reopen_it():
    """A resumed save (P5.1) restores the turn window. Opening the scene again would
    narrate the party arriving somewhere they have been standing for an hour."""
    table = Paper()
    subject = session()
    subject.open_scene(table)
    before = len(subject.campaign.history)

    assert subject.open_scene(table) is None
    assert len(subject.campaign.history) == before


def test_a_seat_that_cannot_be_reached_raises_rather_than_prints():
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("cannot reach the seat")

    with pytest.raises(SessionError, match="cannot reach"):
        session(Dead()).open_scene(Paper())


# --- a turn ----------------------------------------------------------------


def test_a_turn_goes_through_the_gm_and_into_the_history():
    table = Paper()
    subject = session(MockBackend(["You are soaked.", "The current takes your knee."]))
    subject.open_scene(table)

    result = subject.take_turn("I wade in", table)

    assert result is not None
    assert len(subject.campaign.history) == 2
    assert subject.player_turns == 1


def test_a_failed_turn_is_reported_and_costs_no_history():
    class Flaky(MockBackend):
        def __init__(self):
            super().__init__(["The ford is loud tonight."])
            self.calls_made = 0

        def generate(self, request, on_text=None):
            self.calls_made += 1
            if self.calls_made > 1:
                raise RuntimeError("connection reset")
            return super().generate(request, on_text)

    table = Paper()
    subject = session(Flaky())
    subject.open_scene(table)
    before = len(subject.campaign.history)

    assert subject.take_turn("I wade in", table) is None
    assert len(subject.campaign.history) == before
    assert "error" in table.kinds()


def test_the_table_is_asked_about_items_on_every_turn():
    """P2.4 puts the sheets in the players' hands. A front end that forgot to ask would
    be a front end where the GM hands out gear unilaterally."""
    table = Paper()
    subject = session(MockBackend(["The ford is loud.", "You find a coil of rope."]))
    subject.open_scene(table)
    subject.take_turn("I look around", table)

    assert table.kinds().count("inventory") == 2


# --- who holds the keyboard ------------------------------------------------


def test_the_first_member_takes_the_first_seat():
    assert session(party=("Brannoc", "Corin")).acting == "Brannoc"


def test_the_seat_can_be_handed_over():
    subject = session(party=("Brannoc", "Corin"))

    subject.hand_to("Corin")

    assert subject.member.name == "Corin"
    assert subject.sheet.name == "Corin"


def test_a_resumed_save_names_who_was_playing():
    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet("Corin"))])

    class Resumed:
        acting = "Corin"

    assert acting_member(campaign, Resumed()) == "Corin"


def test_a_save_naming_somebody_who_left_falls_back_to_the_party():
    """A save outlives the character it names — a sheet renamed, a player retiring
    somebody. Handing the prompt to a character who is not in the room would end the
    session before it started."""
    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet("Brannoc"))])

    class Resumed:
        acting = "Somebody Else"

    assert acting_member(campaign, Resumed()) == "Brannoc"


# --- ending ----------------------------------------------------------------


def test_the_sweep_runs_before_the_chronicle():
    """Both are independent, but the sweep is the cheap confirmable one and the ledger is
    the instrument this project measures drift with. An end-of-session cut short should
    lose the summary, which regenerates for free, and not the facts."""
    table = Paper()
    subject = session()
    subject.open_scene(table)

    subject.finish(table)

    kinds = table.kinds()
    assert kinds.index("sweep") < kinds.index("chronicle")


@pytest.mark.parametrize("job", ["sweep", "chronicle"])
def test_either_job_can_be_switched_off(job):
    table = Paper()
    subject = session()
    subject.open_scene(table)

    subject.finish(table, **{job: False})

    assert job not in table.kinds()


def test_an_evening_where_nothing_happened_runs_neither():
    table = Paper()

    session().finish(table)

    assert "sweep" not in table.kinds() and "chronicle" not in table.kinds()


def test_the_save_is_closed_even_when_nothing_was_played(tmp_path):
    """Closing is what distinguishes a bedtime from a crash (P5.1), and a session where
    nobody said anything is still a bedtime."""
    saves = SaveStore(tmp_path / "state.yaml", "ford-crossing")
    subject = session(saves=saves)

    subject.finish(Paper())

    assert saves.load().closed is True


def test_a_save_is_written_every_turn_and_not_just_at_the_end(tmp_path):
    saves = SaveStore(tmp_path / "state.yaml", "ford-crossing")
    table = Paper()
    subject = session(MockBackend(["The ford is loud.", "You are soaked."]), saves=saves)
    subject.open_scene(table)
    subject.take_turn("I wade in", table)

    save = saves.load()
    assert save.closed is False
    assert len(save.turns) == 2


def test_closing_releases_the_seats_and_is_safe_twice():
    closer = _Closer()
    subject = session(closers=[closer])

    subject.close()
    subject.close()

    assert closer.closed == 1


# --- small parts -----------------------------------------------------------


def test_a_requested_seed_is_used_and_a_missing_one_is_drawn():
    assert draw_seed(7) == 7
    assert isinstance(draw_seed(None), int)


def test_resuming_where_there_is_no_save_is_not_an_error(tmp_path):
    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet())])

    assert resume_from(SaveStore(tmp_path / "state.yaml", "ford-crossing"), campaign) is None


def test_an_explicit_scene_beats_what_the_save_remembered(tmp_path):
    """Somebody typing `--scene` is deliberately moving the party."""
    saves = SaveStore(tmp_path / "state.yaml", "ford-crossing")
    first = session(saves=saves, scene="the ford")
    first.record()

    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet())])
    resume_from(saves, campaign, scene="the mill road")

    assert campaign.scene == "the mill road"


def test_without_one_the_save_says_where_they_were_standing(tmp_path):
    saves = SaveStore(tmp_path / "state.yaml", "ford-crossing")
    session(saves=saves, scene="the ford").record()

    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet())])
    resume_from(saves, campaign)

    assert campaign.scene == "the ford"


def test_the_engine_builder_hands_both_front_ends_the_same_engine():
    campaign = CampaignContext(name="Ford", party=[PartyMember.from_sheet(sheet())])
    backend = MockBackend()

    engine = build_engine(
        campaign, backend, log=None, scaffolding="off", seed=3,
        max_tokens=512, billing="api", prices={}, canon=None,
    )

    assert engine.builder.scaffolding == "off"
    assert engine.campaign is campaign
