"""The drift baseline — "the fixture, not the seed" (Fable, 2026-08-15).

P2.6 re-swept an archived log every time it wanted to check survival, so the baseline
moved: 224 facts one run, 269 the next, from the same session. A fixed seed is the
obvious fix and the wrong one — it is hostage to model version, quantization and Ollama
internals, and breaks silently on the first upgrade. A file in git cannot move.

What is defended here:

* **the survival check needs nothing** — no model, no NAS, no logs. It loads a committed
  file and renders it through the real prompt builder, which is what lets it be a test
  instead of an errand;
* **a baseline says how it was made**, because a measurement without provenance is an
  anecdote, and knows when its source log has changed underneath it;
* **recovery stability is a separate number** — a measurement of the model, expected to
  move, kept out of the survival check so its movement contaminates nothing.
"""

from __future__ import annotations

from datetime import date

import pytest

from dndc.analysis.baseline import (
    BASELINE_SUFFIX,
    BaselineProvenance,
    BaselineSource,
    DriftBaseline,
    baseline_path,
    digest,
    load_baselines,
    record,
)
from dndc.analysis.drift import compare, survives
from dndc.gm.canon import CanonEntry, CanonScope

FACTS = [
    "The waystation at Ashmill sits where the salt road bends north.",
    "Halda Orrin has kept the waystation for eleven years.",
    "The mill across the water burned last winter.",
]


def entry(index: int, text: str, turn: int | None = None) -> CanonEntry:
    return CanonEntry(
        id=f"player_known-{index}", text=text, scope=CanonScope.PLAYER_KNOWN, turn=turn
    )


def source(**overrides) -> BaselineSource:
    data = dict(log="20260805-063755.jsonl", sha256="a" * 64, turns=32, campaign="smoke")
    data.update(overrides)
    return BaselineSource(**data)


def provenance(**overrides) -> BaselineProvenance:
    data = dict(recorded=date(2026, 8, 15), model="llama3.1:8b", temperature=0.1)
    data.update(overrides)
    return BaselineProvenance(**data)


def baseline(texts=FACTS, **overrides) -> DriftBaseline:
    return DriftBaseline(
        source=overrides.pop("source", source()),
        provenance=overrides.pop("provenance", provenance()),
        entries=[entry(i, text, turn=i) for i, text in enumerate(texts)],
    )


# --- the artifact -----------------------------------------------------------


def test_a_baseline_round_trips_through_yaml(tmp_path):
    path = baseline().save(tmp_path / f"x{BASELINE_SUFFIX}")
    reloaded = DriftBaseline.load(path)

    assert [e.text for e in reloaded.entries] == FACTS
    assert reloaded.provenance.model == "llama3.1:8b"
    assert reloaded.provenance.recorded == date(2026, 8, 15)


def test_a_baseline_records_how_it_was_made():
    """A measurement whose provenance is unrecorded is an anecdote."""
    made = record(
        [(0, entry(0, FACTS[0]))],
        source(),
        provenance(seed=7, dndc_version="0.1.0", commit_sha="abc123"),
    )
    assert made.provenance.model == "llama3.1:8b"
    assert made.provenance.temperature == 0.1
    assert made.provenance.seed == 7
    assert made.provenance.commit_sha == "abc123"


def test_recording_stamps_each_fact_with_the_turn_it_came_from():
    """The contradiction scan reads the origin turn, and the sweep will not invent one."""
    made = record([(3, entry(0, FACTS[0])), (7, entry(1, FACTS[1]))], source(), provenance())
    assert [e.turn for e in made.entries] == [3, 7]


def test_a_baseline_becomes_a_ledger_the_prompt_builder_can_take():
    assert len(baseline().ledger().active()) == len(FACTS)


def test_established_pairs_are_the_shape_the_contradiction_scan_wants():
    pairs = baseline().established()
    assert pairs[1][0] == 1 and pairs[1][1].text == FACTS[1]


def test_a_baseline_knows_when_its_source_log_changed(tmp_path):
    """An archived log edited or replaced after the fixture was cut would otherwise show
    up as the world mysteriously drifting."""
    log = tmp_path / "session.jsonl"
    log.write_text("{}\n", encoding="utf-8")
    made = baseline(source=source(sha256=digest(log)))

    assert made.matches(log)
    log.write_text("{}\n{}\n", encoding="utf-8")
    assert not made.matches(log)


def test_the_baseline_file_is_named_after_the_log_not_the_campaign(tmp_path):
    """A campaign has many sessions and each one is its own before-picture."""
    path = baseline_path("//nas/logs/20260805-063755.jsonl", tmp_path)
    assert path.name == f"20260805-063755{BASELINE_SUFFIX}"


def test_loading_an_empty_directory_is_not_an_error(tmp_path):
    assert load_baselines(tmp_path) == []


def test_baselines_load_in_a_stable_order(tmp_path):
    baseline(source=source(log="b.jsonl")).save(tmp_path / f"b{BASELINE_SUFFIX}")
    baseline(source=source(log="a.jsonl")).save(tmp_path / f"a{BASELINE_SUFFIX}")
    assert [b.source.log for b in load_baselines(tmp_path)] == ["a.jsonl", "b.jsonl"]


# --- survival, offline ------------------------------------------------------


def test_survival_needs_no_model_and_no_log():
    """The whole point of the fixture. This runs in milliseconds with the GPU box off,
    the NAS unmounted, and the logs gone."""
    survived, missing = survives(baseline().ledger())
    assert survived == len(FACTS) and missing == []


def test_the_committed_baselines_all_survive():
    """The regression test Phase 2 was owed. If this fails, the memory pipeline stopped
    carrying established facts into the prompt — the silent failure D-002 exists to
    prevent, and the reason `dndc drift check` exits non-zero."""
    baselines = load_baselines()
    assert baselines, "no committed baselines in data/drift/"
    for committed in baselines:
        survived, missing = survives(committed.ledger())
        assert missing == [], f"{committed.source.log}: {missing}"
        assert survived == len(committed)


def test_every_committed_baseline_carries_its_provenance():
    for committed in load_baselines():
        assert committed.provenance.model
        assert committed.provenance.temperature is not None
        assert committed.provenance.recorded
        assert len(committed.source.sha256) == 64


def test_the_committed_baselines_are_before_pictures():
    """They predate P2.2, so nothing was being fed back to the GM. That property is what
    makes them a baseline rather than just old data, so it is asserted rather than
    remembered."""
    for committed in load_baselines():
        assert committed.source.tagged == 0


# --- recovery stability -----------------------------------------------------


def test_an_identical_re_sweep_is_wholly_stable():
    entries = [entry(i, text) for i, text in enumerate(FACTS)]
    report = compare(entries, list(entries))

    assert report.identical == len(FACTS)
    assert report.stability == 1.0
    assert report.lost == [] and report.gained == []


def test_the_same_fact_in_different_words_counts_as_recovered():
    """A sweep that finds everything in fresh phrasing is stable in the way that matters.
    Reported apart from an exact match so it is visible which happened."""
    before = [entry(0, "There is a rusty iron rail on the undercroft stair that wobbles.")]
    after = [entry(0, "The undercroft stair has a rusty iron rail that wobbles.")]

    report = compare(before, after)
    assert report.equivalent == 1 and report.identical == 0
    assert report.stability == 1.0


def test_a_fact_the_re_sweep_missed_is_named():
    report = compare([entry(0, FACTS[0]), entry(1, FACTS[1])], [entry(0, FACTS[0])])
    assert report.lost == [FACTS[1]]
    assert report.stability == pytest.approx(0.5)


def test_a_fact_the_re_sweep_found_for_the_first_time_is_named():
    report = compare([entry(0, FACTS[0])], [entry(0, FACTS[0]), entry(1, FACTS[1])])
    assert report.gained == [FACTS[1]]
    assert report.stability == 1.0


def test_one_recovered_fact_cannot_satisfy_two_baseline_facts():
    """Otherwise a sweep that collapsed three facts into one would score as stable."""
    before = [entry(0, FACTS[0]), entry(1, FACTS[0])]
    report = compare(before, [entry(0, FACTS[0])])
    assert report.identical == 1 and len(report.lost) == 1


def test_an_empty_baseline_is_not_a_division_by_zero():
    assert compare([], [entry(0, FACTS[0])]).stability == 0.0


def test_stability_is_reported_as_its_own_number():
    """Fable, 2026-08-15: re-sweeping and diffing is recovery stability, a Phase 7 number
    in its own right rather than noise in the survival check."""
    report = compare([entry(0, FACTS[0]), entry(1, FACTS[1])], [entry(0, FACTS[0])])
    assert "stable" in report.summary()
