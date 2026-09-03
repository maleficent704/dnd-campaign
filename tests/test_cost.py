"""P5.4: what an evening cost, read back off the log."""

from __future__ import annotations

import pytest

from dndc.analysis.cost import (
    SeatCost,
    latest_log,
    logs_in,
    read_campaign,
    read_session,
)
from dndc.game.cli import _duration, main
from dndc.logging import SessionLog
from dndc.schema.events import Cost, SessionMeta


def write_log(tmp_path, rows, campaign="The Salt Road", billing="api", session="20260903-200000"):
    log = SessionLog.open(tmp_path, session_id=session)
    log.emit(SessionMeta, campaign=campaign, dndc_version="0", billing=billing)
    for row in rows:
        log.emit(Cost, **row)
    return log.path


def api(seat="gm", usd=0.01, ms=3000, **extra):
    row = dict(
        seat=seat, model="claude-sonnet-5", billing="api",
        input_tokens=1000, output_tokens=200, usd=usd, latency_ms=ms,
    )
    row.update(extra)
    return row


def local(seat="npc", ms=15000, **extra):
    row = dict(
        seat=seat, model="llama3.3:70b", billing="local",
        input_tokens=800, output_tokens=120, latency_ms=ms,
    )
    row.update(extra)
    return row


# --- adding up -------------------------------------------------------------


def test_calls_are_grouped_by_seat(tmp_path):
    report = read_session(write_log(tmp_path, [api(), api(), local(), local(seat="utility_batch")]))

    assert [seat.seat for seat in report.ordered] == ["gm", "npc", "utility_batch"]
    assert report.seats["gm"].calls == 2
    assert report.seats["gm"].input_tokens == 2000
    assert report.summary.calls == 4


def test_the_seats_come_out_in_the_order_a_turn_uses_them(tmp_path):
    rows = [local(seat="utility_batch"), local(seat="npc"), api(), local(seat="utility_interactive")]

    assert [seat.seat for seat in read_session(write_log(tmp_path, rows)).ordered] == [
        "gm", "npc", "utility_interactive", "utility_batch",
    ]


def test_a_seat_this_build_has_never_heard_of_is_still_reported(tmp_path):
    """The log outlives the code that wrote it."""
    report = read_session(write_log(tmp_path, [api(), api(seat="soothsayer")]))

    assert [seat.seat for seat in report.ordered] == ["gm", "soothsayer"]


def test_a_log_with_no_calls_is_empty_and_not_an_error(tmp_path):
    assert read_session(write_log(tmp_path, [])).empty is True


# --- the two columns that must never merge ---------------------------------


def test_a_subscription_call_is_never_counted_as_money(tmp_path):
    """D-004's toggle is only arguable if the two figures stay apart, and OD-16 says the
    subscription one is not even comparable — it measures headless CC's harness."""
    rows = [api(usd=0.44, would_have_cost=True), api(usd=0.44, would_have_cost=True)]
    report = read_session(write_log(tmp_path, rows, billing="subscription"))

    assert report.summary.usd == 0.0
    assert report.summary.hypothetical_usd == pytest.approx(0.88)
    assert report.seats["gm"].local is False


def test_both_kinds_in_one_log_stay_apart(tmp_path):
    """A session restarted onto the other billing mode (P5.2) is one log with both."""
    rows = [api(usd=0.02), api(usd=0.50, would_have_cost=True)]
    report = read_session(write_log(tmp_path, rows))

    assert report.summary.usd == pytest.approx(0.02)
    assert report.summary.hypothetical_usd == pytest.approx(0.50)


def test_an_unpriced_call_is_counted_rather_than_zeroed(tmp_path):
    """A model missing from `pricing:` must not quietly become part of a total that
    claims to be complete."""
    report = read_session(write_log(tmp_path, [api(usd=0.01), api(usd=None)]))

    assert report.seats["gm"].unpriced == 1
    assert report.seats["gm"].priced == 1
    assert report.summary.unpriced == 1


def test_a_local_seat_is_free_and_says_so(tmp_path):
    report = read_session(write_log(tmp_path, [local(), local()]))

    assert report.seats["npc"].local is True
    assert report.seats["npc"].unpriced == 2
    assert report.summary.usd == 0.0


# --- time, which is the other cost -----------------------------------------


def test_latency_keeps_its_shape(tmp_path):
    """One cold load inside twenty warm calls is the finding, and a mean hides it."""
    rows = [local(ms=1000), local(ms=2000), local(ms=62000)]
    seat = read_session(write_log(tmp_path, rows)).seats["npc"]

    assert seat.median_ms == 2000
    assert seat.slowest_ms == 62000
    assert seat.ms == 65000


def test_a_log_from_before_latency_was_recorded_says_nothing_rather_than_zero(tmp_path):
    """`cost.latency_ms` landed in P4.5; every earlier log has none."""
    seat = read_session(write_log(tmp_path, [api(ms=None)])).seats["gm"]

    assert seat.median_ms is None
    assert seat.slowest_ms is None


@pytest.mark.parametrize(
    "ms, shown",
    [(None, "-"), (450, "0.5s"), (9900, "9.9s"), (11000, "11s"), (65000, "1m 05s")],
)
def test_durations_read_as_a_person_would_say_them(ms, shown):
    assert _duration(ms) == shown


# --- across sessions -------------------------------------------------------


def test_a_campaign_adds_up_its_own_sessions_only(tmp_path):
    write_log(tmp_path, [api()], campaign="The Salt Road", session="20260901-000000")
    write_log(tmp_path, [api(), api()], campaign="The Salt Road", session="20260902-000000")
    write_log(tmp_path, [api()], campaign="Smoke Test", session="20260903-000000")

    report = read_campaign(logs_in(tmp_path), campaign="The Salt Road")

    assert len(report.sessions) == 2
    assert report.seats["gm"].calls == 3


def test_campaign_matching_ignores_case(tmp_path):
    write_log(tmp_path, [api()], campaign="The Salt Road", session="20260901-000000")

    assert read_campaign(logs_in(tmp_path), campaign="the salt road").seats["gm"].calls == 1


def test_logs_are_read_oldest_first_and_the_latest_is_the_last(tmp_path):
    write_log(tmp_path, [api()], session="20260901-000000")
    write_log(tmp_path, [api()], session="20260903-000000")

    assert [path.stem for path in logs_in(tmp_path)] == ["20260901-000000", "20260903-000000"]
    assert latest_log(tmp_path).stem == "20260903-000000"


def test_no_logs_at_all_is_not_an_error(tmp_path):
    assert latest_log(tmp_path) is None


def test_a_restart_is_visible_in_the_report(tmp_path):
    """One evening, two headers (P5.2). A single billing figure could not describe it."""
    log = SessionLog.open(tmp_path, session_id="20260903-200000")
    log.emit(SessionMeta, campaign="The Salt Road", dndc_version="0", billing="api")
    log.emit(Cost, **api())
    log.emit(SessionMeta, campaign="The Salt Road", dndc_version="0", billing="subscription")
    log.emit(Cost, **api(usd=0.4, would_have_cost=True))

    report = read_session(log.path)

    assert report.restarts == 1
    assert report.billing == ("api", "subscription")


def test_seats_of_different_names_cannot_be_added():
    with pytest.raises(ValueError, match="cannot add"):
        SeatCost(seat="gm") + SeatCost(seat="npc")


# --- the command -----------------------------------------------------------


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    from dndc.game import cli

    monkeypatch.setattr(cli, "resolve_log_dir", lambda _: tmp_path)
    return tmp_path


def test_cost_reads_the_newest_session_by_default(log_dir, capsys):
    write_log(log_dir, [api(usd=0.0125)], session="20260901-000000")
    write_log(log_dir, [api(usd=0.0250), local()], session="20260902-000000")

    assert main(["cost"]) == 0

    out = capsys.readouterr().out
    assert "20260902-000000" in out
    assert "$0.0250" in out
    assert "local" in out
    assert "0.0125" not in out


def test_cost_says_what_a_local_seat_took_instead_of_what_it_charged(log_dir, capsys):
    write_log(log_dir, [api(usd=0.01), local(ms=62000)])

    main(["cost"])

    out = capsys.readouterr().out
    assert "1 local call" in out
    assert "1m 02s of it waiting" in out


def test_cost_labels_a_subscription_total_as_not_a_bill(log_dir, capsys):
    write_log(log_dir, [api(usd=0.44, would_have_cost=True)], billing="subscription")

    main(["cost"])

    out = capsys.readouterr().out
    assert "$0.0000 billed" in out
    assert "not a bill" in out
    assert "OD-16" in out


def test_cost_warns_when_the_total_is_only_a_floor(log_dir, capsys):
    write_log(log_dir, [api(usd=0.01), api(usd=None, model="something-unpriced")])

    main(["cost"])

    assert "carried no price" in capsys.readouterr().out


def test_cost_with_no_logs_says_so(log_dir, capsys):
    assert main(["cost"]) == 1
    assert "no session log" in capsys.readouterr().out


def test_cost_for_a_campaign_nobody_has_played_says_so(log_dir, capsys):
    write_log(log_dir, [api()], campaign="The Salt Road")

    assert main(["cost", "--campaign", "Some Other Road"]) == 1
    assert "no logged calls" in capsys.readouterr().out
