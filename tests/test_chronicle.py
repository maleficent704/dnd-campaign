"""P2.5 — the campaign chronicle, D-002's third memory layer.

The ledger says the mill burned down; the chronicle says the party spent an evening
failing to get a straight answer out of the woman who owns it. Session nine's GM needs
both, and can afford neither as a transcript.

What is defended here:

* a summary that names someone the session never mentioned is rejected — the same guard
  the P2.3 sweep needed, for the same live reason;
* no chronicle entry is better than a fabricated one, so rejection means *nothing filed*;
* the chronicle stays bounded — past a cap the oldest entries fold into one, or D-002's
  prompt rule quietly stops being true around session twelve;
* it reaches the GM prompt, subordinate to canon;
* it is not canon, and cannot become canon;
* a session that cannot reach the local box ends normally.
"""

from __future__ import annotations

from datetime import date

import pytest

from dndc.game.cli import _run_chronicle
from dndc.gm.chronicle import Chronicle, ChronicleEntry
from dndc.gm.context import CampaignContext, GMPromptBuilder, PartyMember, Turn
from dndc.logging import SessionLog, read_log
from dndc.memory.chronicle import (
    CHRONICLE_FILENAME,
    MAX_SUMMARY_CHARS,
    ChronicleReport,
    Chronicler,
)
from dndc.memory.grounding import grounded, unknown_names, vocabulary
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.events import EventType

# --- helpers ---------------------------------------------------------------

#: Plausible GM prose. Every summary a test has the model produce is drawn from here,
#: because since the grounding check a summary about people who are not in the session is
#: not a summary — which is the behaviour, not an inconvenience.
NARRATION = (
    "The waystation at Ashmill sits where the salt road bends north. Halda Orrin has kept "
    "it for eleven years and she does not care for questions about the mill across the "
    "water, which burned last winter. She pours the ale, takes the coin, and looks at the "
    "door whenever the wind moves it."
)

SUMMARY = (
    "The party reached the waystation at Ashmill, where Halda Orrin has kept the house "
    "for eleven years. She poured them ale and took their coin, but turned aside every "
    "question about the burned mill across the water. They left with nothing settled."
)


def turns(*narrations: str) -> list[Turn]:
    return [
        Turn(player_input=f"input {index}", narration=text, speaker="Kelly (Corin)")
        for index, text in enumerate(narrations, start=1)
    ]


def session(exchanges: int = 2) -> list[Turn]:
    return turns(*[NARRATION] * exchanges)


def chronicler(backend: MockBackend, **kwargs) -> Chronicler:
    kwargs.setdefault("party", ["Corin Vale"])
    return Chronicler(backend, **kwargs)


def entry(index: int, summary: str = SUMMARY) -> ChronicleEntry:
    return ChronicleEntry(
        id=f"s{index}", summary=summary, sessions=(f"2026080{index}-000000",)
    )


class _DeadBackend(MockBackend):
    def generate(self, request, on_text=None):
        raise GMBackendError("cannot reach http://192.168.50.11:11434")


# --- writing one session's entry -------------------------------------------


def test_a_session_becomes_a_paragraph():
    subject = chronicler(MockBackend([SUMMARY], model="llama3.1:8b"))
    report = subject.record(session(), session="s-1")

    assert report.entry is not None
    assert report.entry.summary == SUMMARY
    assert report.entry.sessions == ("s-1",)
    assert report.entry.model == "llama3.1:8b"
    assert len(subject.chronicle) == 1


def test_a_summary_is_flattened_to_one_block():
    """Stored as prose, not as whatever line breaks the model felt like."""
    subject = chronicler(MockBackend([f"{SUMMARY}\n\n  {SUMMARY}"]))
    report = subject.record(session(), session="s-1")
    assert "\n" not in report.entry.summary


def test_an_over_long_summary_is_cut_at_a_sentence_break():
    """An over-long summary is a verbose model, not a wrong one — so it is trimmed
    rather than thrown away, and never stored as half a sentence."""
    long = " ".join([SUMMARY] * 6)
    assert len(long) > MAX_SUMMARY_CHARS
    report = chronicler(MockBackend([long])).record(session(), session="s-1")

    assert len(report.entry.summary) <= MAX_SUMMARY_CHARS
    assert report.entry.summary.endswith(".")


def test_an_empty_session_is_not_written_up():
    subject = chronicler(MockBackend([SUMMARY]))
    assert subject.record([], session="s-1").entry is None
    assert len(subject.chronicle) == 0


def test_a_session_already_in_the_chronicle_is_not_written_twice():
    """A second run would file the evening twice and double its weight in every later
    prompt."""
    existing = Chronicle(entries=[ChronicleEntry(id="s-1", summary=SUMMARY, sessions=("s-1",))])
    subject = chronicler(MockBackend([SUMMARY]), chronicle=existing)

    report = subject.record(session(), session="s-1")

    assert report.already_covered and report.entry is None
    assert len(subject.chronicle) == 1


def test_a_refusal_writes_nothing():
    subject = chronicler(MockBackend(["   "]))
    assert subject.record(session(), session="s-1").entry is None


# --- the grounding guard ---------------------------------------------------


def test_a_summary_that_invents_a_name_is_rejected():
    """The live failure the sweep hit: a small model handed a tight prompt answers with
    names from somewhere other than the text it was given."""
    invented = "The party met Maren Aldis at the harbour and agreed to sail at dawn."
    subject = chronicler(MockBackend([invented], repeat_last=True))

    report = subject.record(session(), session="s-1")

    assert report.entry is None
    assert "Maren" in report.invented
    assert len(subject.chronicle) == 0


def test_the_retry_is_told_which_names_failed():
    """The cheapest useful correction: being shown the word is usually enough."""
    backend = MockBackend(
        ["The party met Maren Aldis at the harbour.", SUMMARY], repeat_last=False
    )
    subject = chronicler(backend)

    report = subject.record(session(), session="s-1")

    assert report.entry is not None and report.calls == 2
    assert "Maren" in backend.calls[1].system


def test_only_one_retry():
    backend = MockBackend(["The party met Maren Aldis at the harbour."], repeat_last=True)
    report = chronicler(backend).record(session(), session="s-1")
    assert report.calls == 2 and report.entry is None


def test_a_party_member_who_did_nothing_is_not_an_invention():
    """A character can belong in a sentence about the party without appearing in the
    night's narration."""
    summary = "Brother Hammond stayed with the horses while the others went in."
    subject = chronicler(
        MockBackend([summary]), party=["Corin Vale", "Brother Hammond"]
    )
    assert subject.record(session(), session="s-1").entry is not None


def test_a_sentence_initial_capital_is_not_a_name():
    subject = chronicler(MockBackend(["They left. Nothing was settled. She took the coin."]))
    assert subject.record(session(), session="s-1").entry is not None


# --- the fold --------------------------------------------------------------


def test_the_chronicle_folds_once_it_outgrows_the_cap():
    """Without this the chronicle is a growing transcript in slow motion, which is the
    exact thing D-002's prompt rule exists to prevent."""
    existing = Chronicle(entries=[entry(i) for i in range(1, 9)])
    folded_text = "Over several nights the party worked the salt road as far as Ashmill."
    subject = chronicler(
        MockBackend([SUMMARY, folded_text], repeat_last=False),
        chronicle=existing,
        max_entries=8,
        fold_oldest=4,
    )

    report = subject.record(session(), session="s-9")

    assert report.folded is not None
    assert report.folded.summary == folded_text
    # Eight entries, plus tonight, minus the four that became one.
    assert len(subject.chronicle) == 6
    assert subject.chronicle.entries[0].folded


def test_a_fold_covers_every_session_it_replaced():
    existing = Chronicle(entries=[entry(i) for i in range(1, 9)])
    subject = chronicler(
        MockBackend([SUMMARY, "They worked the salt road as far as Ashmill."], repeat_last=False),
        chronicle=existing,
        max_entries=8,
        fold_oldest=4,
    )

    report = subject.record(session(), session="s-9")

    assert report.folded.sessions == tuple(f"2026080{i}-000000" for i in range(1, 5))
    assert subject.chronicle.covers("20260801-000000")


def test_nothing_folds_below_the_cap():
    subject = chronicler(
        MockBackend([SUMMARY]), chronicle=Chronicle(entries=[entry(1)]), max_entries=8
    )
    assert subject.record(session(), session="s-2").folded is None


def test_a_failed_fold_does_not_lose_tonight():
    """A fold is housekeeping. The session's own entry is already filed and stays filed."""
    existing = Chronicle(entries=[entry(i) for i in range(1, 9)])
    subject = chronicler(
        MockBackend([SUMMARY, "   "], repeat_last=False),
        chronicle=existing,
        max_entries=8,
    )

    report = subject.record(session(), session="s-9")

    assert report.entry is not None and report.folded is None
    assert len(subject.chronicle) == 9


def test_a_fold_may_only_use_what_the_entries_it_replaces_said():
    """Compression, not recollection — there is nothing it knows that the text does not."""
    existing = Chronicle(entries=[entry(i) for i in range(1, 9)])
    subject = chronicler(
        MockBackend([SUMMARY, "They sailed from Coldharbour with Maren Aldis."], repeat_last=True),
        chronicle=existing,
        max_entries=8,
    )

    report = subject.record(session(), session="s-9")
    assert report.folded is None


def test_folding_drops_the_originals_rather_than_keeping_them():
    """Unlike superseded canon, which is the record of what used to be true. A pre-fold
    summary is just a longer version of the text replacing it, and the log has every word."""
    chronicle = Chronicle(entries=[entry(1), entry(2), entry(3)])
    folded = ChronicleEntry(id="f", summary="One paragraph.", sessions=("a", "b"))

    chronicle.replace(["s1", "s2"], folded)

    assert [e.id for e in chronicle] == ["f", "s3"]


def test_folding_something_that_is_not_there_is_an_error():
    chronicle = Chronicle(entries=[entry(1)])
    with pytest.raises(KeyError):
        chronicle.replace(["nope"], ChronicleEntry(id="f", summary="x"))


# --- persistence -----------------------------------------------------------


def test_an_entry_survives_the_process(tmp_path):
    subject = chronicler(MockBackend([SUMMARY]), path=tmp_path / CHRONICLE_FILENAME)
    subject.record(session(), session="s-1", today=date(2026, 8, 14))

    reloaded = Chronicle.load(tmp_path / CHRONICLE_FILENAME)
    assert reloaded.entries[0].summary == SUMMARY
    assert reloaded.entries[0].created == date(2026, 8, 14)


def test_a_scratch_session_writes_no_file_and_still_logs(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = chronicler(MockBackend([SUMMARY]), log=log)

    subject.record(session(), session="s-1")

    assert not (tmp_path / CHRONICLE_FILENAME).exists()
    assert any(e.type is EventType.CHRONICLE_WRITE for e in read_log(log.path))


def test_for_campaign_reads_the_file_it_will_write(tmp_path):
    Chronicle(entries=[entry(1)]).save(tmp_path / CHRONICLE_FILENAME)
    subject = Chronicler.for_campaign(MockBackend([SUMMARY]), tmp_path)
    assert len(subject.chronicle) == 1


# --- logging ---------------------------------------------------------------


def test_the_entry_is_logged_as_a_chronicle_write(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = chronicler(MockBackend([SUMMARY], model="llama3.1:8b"), log=log)

    subject.record(session(), session="s-1")

    event = next(e for e in read_log(log.path) if e.type is EventType.CHRONICLE_WRITE)
    assert event.covers_sessions == ("s-1",)
    assert event.summary == SUMMARY
    assert event.model == "llama3.1:8b"
    assert event.token_estimate == len(SUMMARY) // 4


def test_a_chronicle_entry_is_never_a_canon_write(tmp_path):
    """D-008 keeps these separate families precisely so a lossy summary cannot enter the
    ledger as an established fact."""
    log = SessionLog.open(tmp_path)
    chronicler(MockBackend([SUMMARY]), log=log).record(session(), session="s-1")

    assert not any(e.type is EventType.CANON_WRITE for e in read_log(log.path))


def test_the_call_is_logged_as_a_free_local_cost_row(tmp_path):
    log = SessionLog.open(tmp_path)
    chronicler(MockBackend([SUMMARY], model="llama3.1:8b"), log=log).record(
        session(), session="s-1"
    )

    cost = next(e for e in read_log(log.path) if e.type is EventType.COST)
    assert (cost.seat, cost.model, cost.billing) == ("utility_batch", "llama3.1:8b", "local")
    assert cost.would_have_cost is False


# --- failure ---------------------------------------------------------------


def test_an_unreachable_box_ends_the_session_quietly(tmp_path):
    subject = chronicler(_DeadBackend(), path=tmp_path / CHRONICLE_FILENAME)
    report = subject.record(session(), session="s-1")

    assert not report.ran and "192.168.50.11" in report.error
    assert report.entry is None
    assert not (tmp_path / CHRONICLE_FILENAME).exists()


def test_an_unexpected_error_is_also_caught():
    class _Broken(MockBackend):
        def generate(self, request, on_text=None):
            raise ValueError("nonsense from the box")

    report = chronicler(_Broken()).record(session(), session="s-1")
    assert not report.ran and "ValueError" in (report.error or "")


# --- the prompt ------------------------------------------------------------


def test_the_chronicle_reaches_the_gm_prompt():
    campaign = CampaignContext(
        name="The Salt Road",
        party=[PartyMember(name="Corin Vale", player="Kelly")],
        chronicle=Chronicle(entries=[entry(1)]),
    )
    state = GMPromptBuilder().campaign_state(campaign)
    assert SUMMARY in state


def test_the_prompt_says_canon_outranks_the_chronicle():
    """The ratified contradiction rule, applied to the layer most likely to be wrong.

    A chronicle entry is compressed prose written by an 8B; the ledger is what the GM
    declared and a human confirmed. Where they disagree the prompt has to say which wins,
    or the cheapest layer silently outranks the most expensive one.
    """
    state = GMPromptBuilder().campaign_state(CampaignContext(name="c"))
    flat = " ".join(state.replace("**", "").split()).lower()
    assert "canon wins" in flat
    assert "recollection, not record" in flat


def test_an_empty_chronicle_says_so_rather_than_leaving_a_hole():
    state = GMPromptBuilder().campaign_state(CampaignContext(name="c"))
    assert "this is the first session" in state


def test_the_chronicle_is_ordered_oldest_first():
    chronicle = Chronicle(entries=[entry(1, "First night."), entry(2, "Second night.")])
    assert chronicle.render() == "First night.\n\nSecond night."


# --- the grounding helpers, shared with the sweep --------------------------


def test_grounding_accepts_an_honest_paraphrase():
    known = vocabulary(NARRATION)
    assert grounded("Halda Orrin has kept the waystation for eleven years.", known)


def test_grounding_rejects_a_name_from_nowhere():
    """"Maren" is not listed because it opens the sentence, and a sentence-initial capital
    is not evidence of a name. One half of an invented name is enough to reject it, so
    buying the other half would cost a false positive on every sentence starting with
    "They"."""
    assert unknown_names("Maren Aldis keeps the waystation.", vocabulary(NARRATION)) == [
        "Aldis"
    ]


def test_grounding_ignores_the_first_word_of_every_sentence():
    known = vocabulary(NARRATION)
    assert unknown_names("They left. Nothing was settled.", known) == []


# --- the CLI wrapper -------------------------------------------------------


def _campaign() -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        party=[PartyMember(name="Corin Vale", player="Kelly")],
        history=session(),
    )


def test_the_cli_says_when_the_summary_invented_someone(monkeypatch, tmp_path, capsys):
    """Which names failed is the useful part — it measures the seat rather than being a
    mystery."""
    from rich.console import Console

    monkeypatch.setattr(
        "dndc.game.cli.build_batch_backend",
        lambda cfg, temperature=None: MockBackend(
            ["The party met Maren Aldis."], repeat_last=True
        ),
    )
    log = SessionLog.open(tmp_path)
    args = type("Args", (), {"campaign": None})()

    _run_chronicle(Console(no_color=True, width=200), _config(), _campaign(), args, log)

    assert "invented" in capsys.readouterr().out


def test_the_cli_prints_the_summary(monkeypatch, tmp_path, capsys):
    from rich.console import Console

    monkeypatch.setattr(
        "dndc.game.cli.build_batch_backend",
        lambda cfg, temperature=None: MockBackend([SUMMARY]),
    )
    log = SessionLog.open(tmp_path)
    args = type("Args", (), {"campaign": None})()

    _run_chronicle(Console(no_color=True, width=200), _config(), _campaign(), args, log)

    assert "Ashmill" in capsys.readouterr().out


def _config():
    from dndc.config import load_config

    return load_config()
