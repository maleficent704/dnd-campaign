"""P0.5: the append-only JSONL session log."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dndc.logging import (
    SessionLog,
    events_of,
    git_commit_sha,
    iter_raw,
    new_session_id,
    next_seq_for,
    read_log,
    resolve_log_dir,
)
from dndc.schema.events import (
    DiceRoll,
    EventType,
    GMNarration,
    PlayerInput,
    RulesResolution,
    SessionMeta,
)


@pytest.fixture
def log(tmp_path) -> SessionLog:
    return SessionLog.open(tmp_path, session_id="test-session")


def test_emit_assigns_monotonic_seq(log):
    first = log.emit(PlayerInput, player="Kelly", text="I open the door")
    second = log.emit(PlayerInput, player="Sam", text="I follow")
    assert (first.seq, second.seq) == (0, 1)
    assert log.seq == 2


def test_emit_fills_in_the_session_id(log):
    event = log.emit(PlayerInput, player="Kelly", text="hi")
    assert event.session_id == "test-session"


def test_one_json_object_per_line(log):
    log.emit(PlayerInput, player="Kelly", text="a")
    log.emit(PlayerInput, player="Sam", text="b")
    lines = log.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["type"] == "player_input" for line in lines)


def test_events_round_trip_as_typed_objects(log):
    log.emit(
        RulesResolution,
        kind="check",
        dc=15,
        seed=7,
        roll=DiceRoll(expression="1d20+3", rolls=(11,), kept=(11,), modifier=3, total=14),
    )
    (restored,) = read_log(log.path)
    assert isinstance(restored, RulesResolution)
    assert restored.dc == 15
    assert restored.roll.rolls == (11,)
    assert restored.seed == 7


def test_none_fields_are_omitted_rather_than_written_as_null(log):
    log.emit(PlayerInput, player="Kelly", text="hi")
    record = json.loads(log.path.read_text(encoding="utf-8").strip())
    assert "character" not in record


def test_reopening_resumes_the_seq_counter(tmp_path):
    """The npc-village rider: a process restart must not reuse seq numbers."""
    first = SessionLog.open(tmp_path, session_id="s")
    first.emit(PlayerInput, player="Kelly", text="a")
    first.emit(PlayerInput, player="Kelly", text="b")

    resumed = SessionLog.open(tmp_path, session_id="s")
    assert resumed.seq == 2
    event = resumed.emit(PlayerInput, player="Sam", text="c")
    assert event.seq == 2

    seqs = [e.seq for e in read_log(first.path)]
    assert seqs == [0, 1, 2]


def test_reopening_appends_rather_than_truncating(tmp_path):
    """The log is the research record; a rewritten log is a corrupted experiment."""
    first = SessionLog.open(tmp_path, session_id="s")
    first.emit(PlayerInput, player="Kelly", text="original")
    SessionLog.open(tmp_path, session_id="s").emit(PlayerInput, player="Sam", text="later")

    texts = [e.text for e in read_log(first.path)]
    assert texts == ["original", "later"]


def test_next_seq_for_a_new_log_is_zero(tmp_path):
    assert next_seq_for(tmp_path / "absent.jsonl") == 0


def test_a_truncated_final_line_does_not_break_the_rest(tmp_path):
    """A hard crash mid-write must not cost the whole session."""
    log = SessionLog.open(tmp_path, session_id="s")
    log.emit(PlayerInput, player="Kelly", text="a")
    log.emit(PlayerInput, player="Sam", text="b")
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write('{"type": "player_input", "seq": 2, "sess')

    assert [e.text for e in read_log(log.path)] == ["a", "b"]
    assert len(list(iter_raw(log.path))) == 2


def test_blank_lines_are_skipped(tmp_path):
    log = SessionLog.open(tmp_path, session_id="s")
    log.emit(PlayerInput, player="Kelly", text="a")
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write("\n\n")
    assert len(read_log(log.path)) == 1


def test_events_of_filters_by_family(log):
    log.emit(SessionMeta, dndc_version="0.1.0", billing="api")
    log.emit(PlayerInput, player="Kelly", text="a")
    log.emit(GMNarration, text="The hall is cold.")
    assert len(events_of(log.path, EventType.PLAYER_INPUT)) == 1
    assert len(events_of(log.path, EventType.SESSION_META)) == 1


def test_unicode_survives_the_round_trip(log):
    log.emit(GMNarration, text="The naïve façade — a dragon’s hoard")
    (event,) = read_log(log.path)
    assert "naïve façade" in event.text


def test_session_id_is_timestamp_shaped():
    from datetime import datetime, timezone

    stamped = new_session_id(datetime(2026, 7, 27, 20, 5, 9, tzinfo=timezone.utc))
    assert stamped == "20260727-200509"


def test_log_directory_is_created_on_demand(tmp_path):
    nested = tmp_path / "a" / "b" / "logs"
    log = SessionLog.open(nested, session_id="s")
    log.emit(PlayerInput, player="Kelly", text="hi")
    assert log.path.exists()


# --- commit sha ------------------------------------------------------------


def test_commit_sha_is_none_outside_a_git_repo(tmp_path):
    sha, dirty = git_commit_sha(tmp_path)
    assert sha is None and dirty is False


def test_commit_sha_is_read_from_a_real_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    sha, dirty = git_commit_sha(tmp_path)
    assert sha is not None and len(sha) == 40
    assert dirty is False

    (tmp_path / "f.txt").write_text("changed", encoding="utf-8")
    _, dirty_now = git_commit_sha(tmp_path)
    assert dirty_now is True


# --- log dir resolution ----------------------------------------------------


def test_relative_log_dir_resolves_against_the_repo_root(tmp_path):
    assert resolve_log_dir("logs/", root=tmp_path) == tmp_path / "logs"


def test_absolute_log_dir_is_left_alone(tmp_path):
    assert resolve_log_dir(str(tmp_path / "elsewhere")) == tmp_path / "elsewhere"


# --- the stdlib name shadow (confirmation owed to Fable, 2026-07-27) --------


def test_dndc_logging_does_not_shadow_the_stdlib_in_process():
    import logging as stdlib_logging

    import dndc.logging

    assert sys.modules["logging"] is stdlib_logging
    assert dndc.logging is not stdlib_logging
    assert stdlib_logging.getLogger("dndc-test").name == "dndc-test"


def test_absolute_import_of_logging_resolves_to_the_stdlib_after_importing_ours():
    """The decisive check: a fresh interpreter, our package imported first."""
    script = (
        "import dndc.logging;"
        "import logging;"
        "print(logging.__file__);"
        "print(hasattr(logging, 'getLogger'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    module_path, has_getlogger = result.stdout.strip().splitlines()
    assert has_getlogger == "True"
    assert "dndc" not in module_path.replace("\\", "/").split("/site-packages/")[-1]
    assert module_path.endswith("logging/__init__.py") or module_path.endswith(
        "logging\\__init__.py"
    )


def test_a_new_session_never_lands_inside_an_existing_log(tmp_path, monkeypatch):
    """Ids are second-resolution, so two runs in one second would share a file.

    P5.1 made this matter: a *resumed* session deliberately reopens its own log, so a
    new one arriving in an old file would be indistinguishable from a restart that
    never happened.
    """
    monkeypatch.setattr("dndc.logging.emitter.new_session_id", lambda: "20260903-201500")

    first = SessionLog.open(tmp_path)
    first.emit(PlayerInput, player="Kelly", text="hi")
    second = SessionLog.open(tmp_path)

    assert second.session_id == "20260903-201500-2"
    assert second.path != first.path
    assert second.seq == 0
