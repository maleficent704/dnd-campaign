"""P2.6 — the drift test, and the instrument Phase 2 was built to make possible.

D-002's rationale is that "without the ledger, established facts mutate within one
session". That is a claim until something counts, and this is the thing that counts.

Two halves, and the tests treat them differently on purpose:

* **survival is deterministic** — a fact established in a session must reach the prompt
  the next session would send. No model, no tolerance, no flake. A hole here is the
  silent failure the whole phase exists to prevent;
* **contradiction is judged** — so what is defended is not the verdict but the guards:
  the judge is only asked about facts the passage touches, and a claimed contradiction
  that cannot be quoted from the passage is thrown out and counted.
"""

from __future__ import annotations

import pytest

from dndc.analysis.drift import (
    Contradiction,
    ContradictionScan,
    DriftReport,
    measure,
    recover,
    store_for_replay,
    survives,
)
from dndc.analysis.replay import clean, replay, replay_turns
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, GMPromptBuilder, Turn
from dndc.logging import SessionLog
from dndc.memory.sweep import CanonSweep
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.events import CallStatus, GMNarration, PlayerInput, SessionMeta

# --- helpers ---------------------------------------------------------------

NARRATION = (
    "The waystation at Ashmill sits where the salt road bends north. Halda Orrin has kept "
    "it for eleven years, and the mill across the water burned last winter."
)


def write_log(tmp_path, exchanges, campaign="The Salt Road", tags=()):
    """A session log as `dndc play` would have written it."""
    log = SessionLog.open(tmp_path)
    log.emit(SessionMeta, campaign=campaign, dndc_version="0", billing="api")
    for index, (said, narrated) in enumerate(exchanges):
        if said:
            log.emit(PlayerInput, player="Kelly", character="Corin Vale", text=said)
        text = narrated
        if index < len(tags) and tags[index]:
            text = f"{text} [[CANON: {tags[index]}]]"
        log.emit(GMNarration, text="", status=CallStatus.PENDING, call_id=f"c{index}")
        log.emit(
            GMNarration, text=text, status=CallStatus.COMPLETE, call_id=f"c{index}"
        )
    return log.path


def turns(*narrations: str) -> list[Turn]:
    return [
        Turn(player_input=f"input {i}", narration=text, speaker="Kelly (Corin Vale)")
        for i, text in enumerate(narrations, start=1)
    ]


def ledger_of(*texts: str) -> CanonLedger:
    return CanonLedger(
        entries=[
            CanonEntry(id=f"e{i}", text=text, scope=CanonScope.PLAYER_KNOWN)
            for i, text in enumerate(texts, start=1)
        ]
    )


def sweeping(backend: MockBackend, **kwargs) -> CanonSweep:
    kwargs.setdefault("chunk_turns", 1)
    return CanonSweep(backend, store_for_replay(), **kwargs)


# --- replay ----------------------------------------------------------------


def test_a_logged_session_comes_back_as_turns(tmp_path):
    path = write_log(tmp_path, [("I go in", NARRATION), ("I ask her", NARRATION)])
    session = replay(path)

    assert len(session.turns) == 2
    assert session.turns[0].player_input == "I go in"
    assert session.campaign == "The Salt Road"


def test_replay_strips_the_tags_the_table_never_saw(tmp_path):
    """Replaying with tags left in would feed the sweep a transcript nobody played."""
    path = write_log(tmp_path, [("I go in", NARRATION)], tags=["The mill burned down."])
    session = replay(path)

    assert "[[CANON" not in session.turns[0].narration
    assert session.tagged == [(0, "The mill burned down.")]


def test_replay_cleans_exactly_as_the_turn_loop_does():
    text = "You push it open. [[CHECK: Strength DC 12 — it sticks]] [[GAIN: iron key]]"
    assert clean(text) == "You push it open."


def test_a_pending_narration_is_not_a_turn(tmp_path):
    """A crashed call logs intent before the call (OD-9). It is not an exchange."""
    log = SessionLog.open(tmp_path)
    log.emit(SessionMeta, dndc_version="0", billing="api")
    log.emit(GMNarration, text="", status=CallStatus.PENDING, call_id="c1")
    log.emit(GMNarration, text="", status=CallStatus.FAILED, call_id="c1")

    assert replay(log.path).turns == []


def test_a_reply_that_was_only_a_check_request_is_not_a_turn(tmp_path):
    path = write_log(tmp_path, [("I climb", "[[CHECK: Strength DC 12 — you slip]]")])
    assert replay(path).turns == []


def test_the_opening_scene_is_marked_as_one(tmp_path):
    path = write_log(tmp_path, [("", NARRATION), ("I go in", NARRATION)])
    session = replay(path)
    assert session.turns[0].opening and not session.turns[1].opening


def test_the_party_is_read_off_the_speakers(tmp_path):
    path = write_log(tmp_path, [("I go in", NARRATION)])
    assert replay(path).party == ("Corin Vale",)


def test_several_logs_replay_as_one_run(tmp_path):
    first = write_log(tmp_path / "a", [("I go in", NARRATION)])
    second = write_log(tmp_path / "b", [("I ask", NARRATION), ("I leave", NARRATION)])
    assert len(replay_turns([first, second])) == 3


def test_the_archived_fixtures_shape_is_what_the_before_picture_means(tmp_path):
    """Pre-P2.2 logs carry no canon tags at all. The drift test has to recover the world
    from narration, which is what makes those logs the baseline rather than a problem."""
    path = write_log(tmp_path, [("I go in", NARRATION)])
    assert replay(path).tagged == []


# --- survival: deterministic ------------------------------------------------


def test_an_established_fact_reaches_the_next_sessions_prompt():
    survived, missing = survives(ledger_of("The mill across the water burned last winter."))
    assert survived == 1 and missing == []


def test_survival_is_measured_through_the_real_prompt_builder():
    """Reading the ledger back would pass with the builder disconnected entirely — which
    is exactly the silent failure D-002 exists to prevent."""
    ledger = ledger_of("Halda Orrin has kept the waystation for eleven years.")
    survived, _ = survives(ledger, party=["Corin Vale"])
    assert survived == 1


def test_a_superseded_fact_is_not_counted_as_lost():
    """Superseded entries stay on file and leave the prompt. Counting them as missing
    would make the instrument report drift every time the world legitimately changed."""
    ledger = ledger_of("The bridge is out.")
    store = store_for_replay()
    store.ledger = ledger
    store.supersede("e1", "The bridge has been rebuilt.")

    survived, missing = survives(ledger)

    assert missing == [] and survived == 1
    # And the replacement is what the prompt now carries, not the original.
    state = GMPromptBuilder().campaign_state(CampaignContext(name="c", ledger=ledger))
    assert "The bridge has been rebuilt." in state
    assert "The bridge is out." not in state


def test_a_gm_only_fact_still_survives_into_the_prompt():
    """The GM owns ground truth, secrets included (D-003) — it is the players' screen
    that must not show them, not the prompt."""
    ledger = CanonLedger(
        entries=[CanonEntry(id="s1", text="The reeve was paid.", scope=CanonScope.GM_ONLY)]
    )
    survived, missing = survives(ledger)
    assert survived == 1 and missing == []


def test_an_empty_ledger_survives_vacuously():
    assert survives(CanonLedger()) == (0, [])


# --- recovery ---------------------------------------------------------------


def test_recovery_records_which_turn_established_each_fact():
    """The sweep refuses to claim a turn number for what it finds — so the drift replay
    sweeps one turn at a time, and the chunking supplies the provenance."""
    backend = MockBackend(
        [
            "[[CANON: The waystation at Ashmill sits where the salt road bends north.]]",
            "[[CANON: The mill across the water burned last winter.]]",
        ],
        repeat_last=False,
    )
    established = recover(turns(NARRATION, NARRATION), sweeping(backend))

    assert [origin for origin, _ in established] == [0, 1]


def test_a_fact_restated_later_belongs_to_the_turn_that_established_it():
    backend = MockBackend(["[[CANON: The mill across the water burned last winter.]]"])
    established = recover(turns(NARRATION, NARRATION, NARRATION), sweeping(backend))
    assert len(established) == 1 and established[0][0] == 0


def test_recovery_stops_cleanly_when_the_box_goes_away():
    class _Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("cannot reach toto-llm")

    assert recover(turns(NARRATION), sweeping(_Dead())) == []


# --- the contradiction scan -------------------------------------------------


BRIDGE = "The bridge at Aldermoor is out."
INTACT = "You cross the bridge at Aldermoor without trouble, the boards firm underfoot."


def scan_with(*responses: str, **kwargs) -> ContradictionScan:
    return ContradictionScan(MockBackend(list(responses), repeat_last=True), **kwargs)


def established_at(turn: int, text: str):
    return [(turn, CanonEntry(id="e1", text=text, scope=CanonScope.PLAYER_KNOWN))]


def test_a_contradiction_the_judge_can_quote_is_reported():
    report = DriftReport(turns=2)
    scan = scan_with(
        f"[[CONTRADICTS: 1 | {INTACT} | the bridge cannot be both out and crossed]]"
    )

    found = scan.scan(turns(BRIDGE, INTACT), established_at(0, BRIDGE), report)

    assert len(found) == 1
    assert found[0].turn == 1 and found[0].fact == BRIDGE
    assert report.unquoted == 0


def test_a_contradiction_the_judge_cannot_quote_is_thrown_out():
    """The guard the sweep's second live run taught: a claim that cannot be found in its
    source is the model writing, not reading."""
    report = DriftReport(turns=2)
    scan = scan_with("[[CONTRADICTS: 1 | They burned the bridge themselves. | conflict]]")

    found = scan.scan(turns(BRIDGE, INTACT), established_at(0, BRIDGE), report)

    assert found == [] and report.unquoted == 1


def test_a_fact_number_out_of_range_is_thrown_out():
    report = DriftReport(turns=2)
    scan = scan_with(f"[[CONTRADICTS: 7 | {INTACT} | conflict]]")

    assert scan.scan(turns(BRIDGE, INTACT), established_at(0, BRIDGE), report) == []
    assert report.unquoted == 1


def test_none_means_none():
    report = DriftReport(turns=2)
    scan = scan_with("NONE")
    assert scan.scan(turns(BRIDGE, INTACT), established_at(0, BRIDGE), report) == []


def test_a_turn_is_never_checked_against_facts_it_established():
    """A fact recovered from turn three cannot be contradicted by turn three — that is
    where it came from."""
    report = DriftReport(turns=1)
    scan = scan_with(f"[[CONTRADICTS: 1 | {INTACT} | conflict]]")

    assert scan.scan(turns(INTACT), established_at(0, BRIDGE), report) == []
    assert report.checked == 0


def test_facts_the_passage_never_touches_are_not_put_to_the_judge():
    """The common case by far. Sending them would bury the question in a list and invite
    the failure the prompt spends half its length warning against."""
    report = DriftReport(turns=2)
    scan = scan_with("NONE")

    scan.scan(
        turns(BRIDGE, "Gulls turn above the harbour wall and the tide is going out."),
        established_at(0, BRIDGE),
        report,
    )
    assert report.checked == 0 and report.skipped == 1


def test_the_judge_sees_only_a_bounded_list():
    report = DriftReport(turns=2)
    backend = MockBackend(["NONE"])
    scan = ContradictionScan(backend, max_facts=2)
    standing = [
        (0, CanonEntry(id=f"e{i}", text=BRIDGE, scope=CanonScope.PLAYER_KNOWN))
        for i in range(5)
    ]

    scan.scan(turns(BRIDGE, INTACT), standing, report)

    assert report.checked == 2 and report.skipped == 3


def test_an_unreachable_box_stops_the_scan_without_raising():
    class _Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("cannot reach toto-llm")

    report = DriftReport(turns=2)
    found = ContradictionScan(_Dead()).scan(
        turns(BRIDGE, INTACT), established_at(0, BRIDGE), report
    )
    assert found == [] and not report.ran


# --- the whole instrument ---------------------------------------------------


def test_measure_reports_survival_and_contradiction_together(tmp_path):
    path = write_log(tmp_path, [("I look", BRIDGE), ("I cross", INTACT)])
    session = replay(path)
    sweep = sweeping(MockBackend([f"[[CANON: {BRIDGE}]]", "NONE"], repeat_last=True))
    scan = scan_with(f"[[CONTRADICTS: 1 | {INTACT} | conflict]]")

    report = measure(session, sweep, scan)

    assert report.turns == 2
    assert report.recovered == 1
    assert report.survived == 1 and report.missing == []
    assert len(report.contradictions) == 1
    assert report.rate == pytest.approx(0.5)


def test_an_empty_session_measures_to_nothing(tmp_path):
    log = SessionLog.open(tmp_path)
    log.emit(SessionMeta, dndc_version="0", billing="api")
    report = measure(replay(log.path), sweeping(MockBackend(["NONE"])))
    assert report.turns == 0 and report.recovered == 0


def test_the_scan_is_optional(tmp_path):
    """`--no-scan`: the deterministic half must be runnable with the GPU box asleep."""
    path = write_log(tmp_path, [("I look", BRIDGE)])
    report = measure(replay(path), sweeping(MockBackend([f"[[CANON: {BRIDGE}]]"])))
    assert report.survived == 1 and report.contradictions == []


def test_the_instrument_never_touches_a_campaign(tmp_path):
    """Read-only in every direction — an analysis run that could write to canon.yaml
    would be an instrument that alters what it measures."""
    path = write_log(tmp_path, [("I look", BRIDGE)])
    store = store_for_replay()
    assert store.path is None

    measure(replay(path), CanonSweep(MockBackend([f"[[CANON: {BRIDGE}]]"]), store, chunk_turns=1))
    assert list(tmp_path.glob("canon.yaml")) == []


def test_the_rate_is_contradictions_per_turn():
    """Fable, 2026-08-14: P2.6 measures live-contradiction frequency before a
    supersession fix is chosen. That frequency is this number."""
    report = DriftReport(turns=8)
    report.contradictions = [
        Contradiction(turn=2, entry_id="e1", fact=BRIDGE, quote=INTACT),
        Contradiction(turn=5, entry_id="e1", fact=BRIDGE, quote=INTACT),
    ]
    assert report.rate == pytest.approx(0.25)
    assert "0.25/turn" in report.summary()


def test_the_rate_of_a_session_with_no_turns_is_zero_not_a_crash():
    assert DriftReport().rate == 0.0


def test_character_creation_is_not_play(tmp_path):
    """P1.4 reuses `gm_narration` with `scene: "character creation"`, and the handoff
    called that field an adequate discriminator for Phase 7 filtering. This is that
    filtering — found by the first live run, on a fixture that turned out to be Sam
    building a character rather than a session of play."""
    log = SessionLog.open(tmp_path)
    log.emit(SessionMeta, dndc_version="0", billing="api")
    log.emit(PlayerInput, player="Sam", text="a big gentle fighter")
    log.emit(
        GMNarration,
        text="Brother Hammond — I love this.",
        status=CallStatus.COMPLETE,
        scene="character creation",
        call_id="c1",
    )
    log.emit(GMNarration, text=NARRATION, status=CallStatus.COMPLETE, call_id="c2")

    session = replay(log.path)

    assert len(session.turns) == 1
    assert session.turns[0].narration == NARRATION


def test_a_creation_turn_does_not_leak_its_player_line_into_the_next_turn(tmp_path):
    """Dropping the narration but keeping the input would attach "a big gentle fighter"
    to whatever the next scene happened to be."""
    log = SessionLog.open(tmp_path)
    log.emit(SessionMeta, dndc_version="0", billing="api")
    log.emit(PlayerInput, player="Sam", text="a big gentle fighter")
    log.emit(
        GMNarration, text="Sounds good.", status=CallStatus.COMPLETE,
        scene="character creation", call_id="c1",
    )
    log.emit(GMNarration, text=NARRATION, status=CallStatus.COMPLETE, call_id="c2")

    turn = replay(log.path).turns[0]
    assert turn.player_input == "" and turn.opening
