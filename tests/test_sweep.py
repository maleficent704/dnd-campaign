"""P2.3 — the end-of-session sweep, the backstop for inline extraction.

The sweep exists because the first P2.2 live run established four facts about the road
and tagged none of them. What is defended here is not that a small model finds facts —
it will, and imperfectly — but that an imperfect writer cannot damage the ledger:

* it can only ever write `player_known`, whatever it claims;
* it never receives a `gm_only` fact, so it cannot echo one to the table;
* it cannot propose anything that is not in the session it read — the guard the second
  live run made necessary, when `llama3.1:8b` answered with the prompt's own examples;
* nothing enters the ledger until a human says so, and what they refuse is written down
  rather than forgotten;
* a sweep that cannot reach the local box ends the session quietly, not in a traceback.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from dndc.game.cli import choose_proposals, parse_selection
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import Turn
from dndc.logging import SessionLog, read_log
from dndc.memory.canon_store import CANON_FILENAME, CanonStore
from dndc.memory.sweep import (
    MAX_FACT_CHARS,
    MAX_PROPOSALS,
    CanonSweep,
    SweepProposal,
    cluster,
)
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.events import CanonSource, EventType

# --- helpers ---------------------------------------------------------------

#: One turn of plausible GM prose. Every fact a test has the sweep propose is drawn from
#: here, because since the grounding check a fact that is not in the transcript is not a
#: proposal at all — which is the behaviour, not an inconvenience.
NARRATION = (
    "The waystation at Ashmill sits where the salt road bends north. Halda Orrin has "
    "kept it for eleven years, and the cracked bell above the door has not been rung in "
    "all that time. Across the water, the mill burned down last winter and nobody has "
    "touched the shell of it since."
)


def turns(*narrations: str) -> list[Turn]:
    return [
        Turn(player_input=f"input {index}", narration=text, speaker="Kelly (Corin)")
        for index, text in enumerate(narrations, start=1)
    ]


def session(exchanges: int = 1) -> list[Turn]:
    return turns(*[NARRATION] * exchanges)


def sweep(backend: MockBackend, store: CanonStore | None = None, **kwargs) -> CanonSweep:
    return CanonSweep(backend, store if store is not None else CanonStore(), **kwargs)


# --- proposing -------------------------------------------------------------


def test_the_sweep_recovers_a_fact_the_gm_did_not_tag():
    backend = MockBackend(["[[CANON: The bell at the Ashmill waystation is cracked.]]"])
    report = sweep(backend).propose(session())

    assert report.ran
    assert [p.text for p in report.proposals] == ["The bell at the Ashmill waystation is cracked."]


def test_preamble_around_the_tags_is_ignored():
    """A small model cannot help saying "Here are the facts I found:" first.

    Sharing the GM's `[[CANON:]]` form is what makes that structural rather than a
    heuristic — anything outside a tag is simply not a fact.
    """
    backend = MockBackend(
        [
            "Sure! Here are the facts I found in the transcript:\n\n"
            "[[CANON: The mill burned down last winter.]]\n"
            "[[CANON: Halda Orrin has kept the waystation for eleven years.]]\n\n"
            "Let me know if you would like me to look again."
        ]
    )
    report = sweep(backend).propose(session())
    assert [p.text for p in report.proposals] == [
        "The mill burned down last winter.",
        "Halda Orrin has kept the waystation for eleven years.",
    ]


def test_a_scope_the_sweep_claims_is_discarded():
    """The load-bearing guard. A local 8B must not be able to mint a secret.

    Not a rule in the prompt — a constant in the code, in the OD-12 tradition: an
    instruction a model follows on turn 3 is one it drops on turn 90.
    """
    backend = MockBackend(
        [
            "[[CANON: gm_only — The mill burned down last winter.]]\n"
            "[[CANON: npc_belief (Halda) — The cracked bell has not been rung.]]"
        ]
    )
    report = sweep(backend).propose(session())
    assert len(report.proposals) == 2
    assert {p.scope for p in report.proposals} == {CanonScope.PLAYER_KNOWN}


def test_what_it_proposes_is_filed_as_player_known_whatever_it_claimed(tmp_path):
    backend = MockBackend(["[[CANON: gm_only — The mill burned down last winter.]]"])
    store = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME)
    subject = sweep(backend, store)

    written = subject.record(subject.propose(session()).proposals)
    assert [entry.scope for entry in written] == [CanonScope.PLAYER_KNOWN]


def test_a_fact_the_ledger_already_holds_is_not_proposed():
    ledger = CanonLedger(
        entries=[
            CanonEntry(
                id="pk-bell",
                text="The cracked bell above the door has not been rung.",
                scope=CanonScope.PLAYER_KNOWN,
            )
        ]
    )
    backend = MockBackend(["[[CANON: the cracked bell above the door has not been rung ]]"])
    report = sweep(backend, CanonStore(ledger)).propose(session())
    assert report.proposals == []


def test_the_same_fact_found_twice_is_proposed_once():
    backend = MockBackend(
        ["[[CANON: The mill burned down last winter.]]\n[[CANON: The mill burned down last winter]]"]
    )
    assert len(sweep(backend).propose(session()).proposals) == 1


def test_a_paragraph_is_not_a_fact():
    backend = MockBackend([f"[[CANON: {'Ashmill ' * (MAX_FACT_CHARS // 4)}]]"])
    assert sweep(backend).propose(session()).proposals == []


def test_a_runaway_sweep_is_capped_and_says_how_much_it_dropped():
    """A silent cap reads as "found everything", which is the one thing it must not."""
    body = "\n".join(
        f"[[CANON: The mill burned down last winter, and so did shed {n}.]]"
        for n in range(MAX_PROPOSALS + 5)
    )
    report = sweep(MockBackend([body])).propose(session())

    assert len(report.proposals) == MAX_PROPOSALS
    assert report.dropped == 5


def test_a_long_session_is_read_in_chunks():
    backend = MockBackend(
        [
            "[[CANON: The mill burned down last winter.]]",
            "[[CANON: The cracked bell has not been rung.]]",
            "[[CANON: Ashmill sits where the salt road bends.]]",
        ],
        repeat_last=False,
    )
    report = sweep(backend, chunk_turns=2).propose(session(6))

    assert report.calls == 3
    assert len(report.proposals) == 3


def test_a_later_chunk_is_told_what_an_earlier_one_found():
    """Otherwise every chunk re-proposes the same establishing facts."""
    backend = MockBackend(
        ["[[CANON: Halda Orrin keeps the waystation.]]", "[[CANON: The mill burned down.]]"],
        repeat_last=False,
    )
    sweep(backend, chunk_turns=1).propose(session(2))

    assert "Halda Orrin keeps the waystation." in backend.calls[1].system


def test_turns_with_no_narration_are_not_swept():
    backend = MockBackend(["NONE"])
    report = sweep(backend).propose([Turn(player_input="hello", narration="   ")])

    assert report.calls == 0
    assert report.proposals == []


def test_an_empty_session_calls_nothing():
    backend = MockBackend(["[[CANON: invented.]]"])
    assert sweep(backend).propose([]).calls == 0


# --- grounding -------------------------------------------------------------


def test_a_name_the_session_never_mentioned_is_thrown_out():
    """The second live run, exactly. Given three worked examples in the prompt,
    `llama3.1:8b` answered with the three worked examples — naming a harbourmaster who
    appears nowhere in the transcript. Prose caused that; prose cannot fix it.
    """
    backend = MockBackend(["[[CANON: Maren Aldis is the harbourmaster at Coldharbour.]]"])
    report = sweep(backend).propose(session())

    assert report.proposals == []
    assert report.ungrounded == 1


def test_an_honest_paraphrase_survives():
    """The check has to be loose enough for real extraction, which never quotes."""
    backend = MockBackend(["[[CANON: Halda Orrin has kept Ashmill's waystation eleven years.]]"])
    report = sweep(backend).propose(session())

    assert len(report.proposals) == 1
    assert report.ungrounded == 0


def test_an_invented_claim_in_familiar_words_is_thrown_out():
    backend = MockBackend(["[[CANON: The chapel crypt holds three sealed reliquaries.]]"])
    assert sweep(backend).propose(session()).proposals == []


def test_grounding_is_measured_per_chunk_not_across_the_session():
    """A fact from exchange 1 must not be able to launder a hallucination in exchange 9."""
    early = "Halda Orrin has kept the Ashmill waystation for eleven years."
    late = "The rain came on hard as the light went out of the sky."
    backend = MockBackend([f"[[CANON: {early}]]"], repeat_last=True)
    report = sweep(backend, chunk_turns=1).propose(turns(early, late))

    assert len(report.proposals) == 1
    assert report.ungrounded == 1


# --- what the sweep is allowed to see --------------------------------------


def test_a_gm_only_fact_is_never_sent_to_the_local_model():
    """Its proposals are printed to the table, so anything it reads is one echo from
    the players' screen. The cheapest fix is not to hand it the secret."""
    ledger = CanonLedger(
        entries=[
            CanonEntry(id="gm-1", text="The reeve took the bribe.", scope=CanonScope.GM_ONLY),
            CanonEntry(id="pk-1", text="The gate is barred.", scope=CanonScope.PLAYER_KNOWN),
        ]
    )
    backend = MockBackend(["NONE"])
    sweep(backend, CanonStore(ledger)).propose(session())

    system = backend.last_request.system
    assert "The gate is barred." in system
    assert "bribe" not in system


def test_the_party_is_named_so_their_actions_are_not_recorded_as_world():
    """A third of the first live run's proposals were what the party did. A small model
    cannot tell a player character from an NPC unless it is told which names are which."""
    backend = MockBackend(["NONE"])
    sweep(backend, party=["Corin Vale", "Brother Hammond"]).propose(session())

    assert "Corin Vale" in backend.last_request.system


def test_the_transcript_carries_the_player_line_for_context():
    backend = MockBackend(["NONE"])
    sweep(backend).propose(session())

    sent = backend.last_request.messages[0].content
    assert "input 1" in sent and "salt road" in sent


def test_the_opening_scene_is_swept_too():
    """It is the turn the P2.2 live run showed tagging nothing at all."""
    backend = MockBackend(["[[CANON: The mill burned down last winter.]]"])
    report = sweep(backend).propose(
        [Turn(player_input="", narration=NARRATION, opening=True)]
    )
    assert len(report.proposals) == 1
    assert "(the session opens)" in backend.last_request.messages[0].content


# --- failure ---------------------------------------------------------------


class _DeadBackend(MockBackend):
    def generate(self, request, on_text=None):
        raise GMBackendError("could not reach Ollama at http://192.168.50.11:11434")


def test_an_unreachable_utility_box_ends_the_session_quietly():
    report = sweep(_DeadBackend()).propose(session())

    assert not report.ran
    assert "could not reach Ollama" in (report.error or "")
    assert report.proposals == []


def test_an_unexpected_error_is_also_caught():
    class _Broken(MockBackend):
        def generate(self, request, on_text=None):
            raise ValueError("nonsense from the box")

    report = sweep(_Broken()).propose(session())
    assert not report.ran and "ValueError" in (report.error or "")


def test_a_failed_sweep_writes_nothing(tmp_path):
    path = tmp_path / CANON_FILENAME
    store = CanonStore(CanonLedger(), path=path)
    subject = sweep(_DeadBackend(), store)

    subject.record(subject.propose(session()).proposals)
    assert not path.exists()


# --- filing ----------------------------------------------------------------


def test_accepted_proposals_are_filed_with_sweep_provenance(tmp_path):
    log = SessionLog.open(tmp_path)
    store = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME, log=log)
    backend = MockBackend(["[[CANON: The mill burned down last winter.]]"], model="llama3.1:8b")
    subject = sweep(backend, store, log=log)

    written = subject.record(subject.propose(session()).proposals, session=log.session_id)

    assert [entry.text for entry in written] == ["The mill burned down last winter."]
    write = next(e for e in read_log(log.path) if e.type is EventType.CANON_WRITE)
    assert write.source is CanonSource.SWEEP
    assert write.confirmed is True
    assert "llama3.1:8b" in (write.established_by or "")


def test_a_declined_proposal_is_logged_and_never_enters_the_ledger(tmp_path):
    """The `inventory_change.confirmed` argument, applied to canon: what a model proposed
    and the table refused measures the proposer, and only if somebody writes it down."""
    log = SessionLog.open(tmp_path)
    path = tmp_path / CANON_FILENAME
    store = CanonStore(CanonLedger(), path=path, log=log)
    subject = sweep(MockBackend(), store, log=log)

    subject.record([], declined=[SweepProposal(text="The reeve is the party's ally.")])

    assert len(store.ledger) == 0
    assert not path.exists()
    write = next(e for e in read_log(log.path) if e.type is EventType.CANON_WRITE)
    assert write.confirmed is False
    assert write.source is CanonSource.SWEEP
    assert write.statement == "The reeve is the party's ally."


def test_a_sweep_fact_claims_no_turn_number(tmp_path):
    """It was established somewhere across the session and the sweep does not know
    where. Inventing provenance is worse than having none."""
    store = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME)
    subject = sweep(MockBackend(["[[CANON: The mill burned down.]]"]), store)

    written = subject.record(subject.propose(session()).proposals, session="s-1")
    assert written[0].turn is None
    assert written[0].session == "s-1"


def test_a_sweep_fact_survives_the_process(tmp_path):
    store = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME)
    subject = sweep(MockBackend(["[[CANON: Halda Orrin keeps the waystation.]]"]), store)
    subject.record(subject.propose(session()).proposals)

    reloaded = CanonStore.for_campaign(tmp_path)
    assert reloaded.holds("Halda Orrin keeps the waystation.", CanonScope.PLAYER_KNOWN)


def test_the_sweep_call_is_logged_as_a_free_local_cost_row(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = sweep(MockBackend(["NONE"], model="llama3.1:8b"), CanonStore(), log=log)
    subject.propose(session())

    cost = next(e for e in read_log(log.path) if e.type is EventType.COST)
    assert (cost.seat, cost.model, cost.billing) == (
        "utility_interactive",
        "llama3.1:8b",
        "local",
    )
    assert cost.would_have_cost is False


# --- the confirmation prompt -----------------------------------------------


@pytest.mark.parametrize("answer", ["", "all", "ALL", " a ", "yes"])
def test_bare_enter_and_its_synonyms_file_everything(answer):
    assert parse_selection(answer, 3) == {1, 2, 3}


@pytest.mark.parametrize("answer", ["none", "n", "0", "skip"])
def test_none_files_nothing(answer):
    assert parse_selection(answer, 3) == set()


@pytest.mark.parametrize(
    "answer,expected",
    [("1 3", {1, 3}), ("2,4", {2, 4}), ("1 3 9", {1, 3}), ("just 2 please", {2})],
)
def test_numbers_pick_individual_facts(answer, expected):
    assert parse_selection(answer, 4) == expected


def test_an_answer_nobody_can_read_is_not_silently_a_refusal():
    """"" and "wat" must not both discard a session's worth of recovered canon."""
    assert parse_selection("wat", 3) is None


def test_the_table_declining_leaves_the_rest_as_declined(monkeypatch):
    proposals = [SweepProposal(text=f"Fact {n}.") for n in (1, 2, 3)]
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "2")

    accepted, declined = choose_proposals(Console(quiet=True), proposals)
    assert [p.text for p in accepted] == ["Fact 2."]
    assert [p.text for p in declined] == ["Fact 1.", "Fact 3."]


def test_nobody_at_the_keyboard_declines_rather_than_files(monkeypatch):
    """A confirmation nobody gave is not a confirmation. The proposals are still
    logged, so the conservative reading costs the record nothing."""
    def _eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("dndc.game.cli.Prompt.ask", _eof)
    accepted, declined = choose_proposals(Console(quiet=True), [SweepProposal(text="Fact.")])
    assert accepted == [] and len(declined) == 1


def test_an_unreadable_answer_is_asked_again(monkeypatch):
    answers = iter(["wat", "1"])
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: next(answers))

    accepted, _ = choose_proposals(Console(quiet=True), [SweepProposal(text="Fact.")])
    assert len(accepted) == 1


# --- display grouping (Fable, 2026-08-14) ----------------------------------


#: The four barking-dog restatements from the 2026-08-13 live run, verbatim. These are
#: what the ruling was about, so they are what the threshold is tuned against.
DOG = [
    "There is a dog barking in the undercroft, sounding insistent and sharp.",
    "There is a dog barking in the undercroft, sounding sharp and insistent as if it has "
    "noticed something or someone approaching.",
]
RAIL = [
    "There is a rusty iron rail on the undercroft stair that wobbles under pressure.",
    "The undercroft stair has a rusty iron rail that wobbles under pressure.",
]


def test_the_same_fact_twice_is_one_line_with_the_other_underneath():
    """The 08-13 live run: 22 proposals for a 3-exchange session, all of them real and
    several of them the same real thing."""
    groups = cluster([SweepProposal(text=text) for text in RAIL])
    assert len(groups) == 1 and len(groups[0]) == 2


def test_grouping_survives_a_rewritten_opening():
    groups = cluster([SweepProposal(text=text) for text in DOG])
    assert len(groups) == 1


def test_two_facts_about_one_subject_are_not_one_fact():
    """Under-clustering costs a longer list; over-clustering hides a fact under an
    indent. Given the choice, take the longer list."""
    groups = cluster(
        [
            SweepProposal(text="The lamp-seller sells lanterns at the top of the stair."),
            SweepProposal(text="The lamp-seller warned against going left at the bottom."),
        ]
    )
    assert len(groups) == 2


def test_a_short_statement_is_never_grouped():
    """"The bridge is out" and "The bridge is fine" share their only long word and are
    opposites. Fuzzy matching must not be able to hide that (npc-village lesson)."""
    groups = cluster(
        [
            SweepProposal(text="The bridge is out."),
            SweepProposal(text="The bridge is fine."),
        ]
    )
    assert len(groups) == 2


def test_grouping_keeps_the_order_the_sweep_proposed_in():
    proposals = [
        SweepProposal(text="The mill across the water burned down last winter."),
        SweepProposal(text=RAIL[0]),
        SweepProposal(text=RAIL[1]),
    ]
    groups = cluster(proposals)
    assert [group[0].text for group in groups] == [proposals[0].text, RAIL[0]]


def test_nothing_is_dropped_by_grouping():
    proposals = [SweepProposal(text=text) for text in DOG + RAIL]
    assert sum(len(group) for group in cluster(proposals)) == len(proposals)


def test_choosing_a_group_files_one_phrasing_and_declines_the_rest(monkeypatch):
    """"The table confirms one phrasing per cluster" — and the phrasings it did not
    confirm are declined, logged, and visible, not silently dropped."""
    proposals = [SweepProposal(text=text) for text in RAIL]
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "1")

    accepted, declined = choose_proposals(Console(quiet=True), proposals)

    assert [p.text for p in accepted] == [RAIL[0]]
    assert [p.text for p in declined] == [RAIL[1]]


def test_declining_a_group_declines_every_phrasing_in_it(monkeypatch):
    proposals = [SweepProposal(text=text) for text in RAIL]
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "none")

    accepted, declined = choose_proposals(Console(quiet=True), proposals)

    assert accepted == []
    assert len(declined) == 2


def test_the_numbers_the_table_types_are_group_numbers(monkeypatch):
    """Four proposals, two facts, so "2" means the second fact — not the second line."""
    proposals = [SweepProposal(text=text) for text in RAIL + DOG]
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "2")

    accepted, _ = choose_proposals(Console(quiet=True), proposals)
    assert [p.text for p in accepted] == [DOG[0]]


def test_the_alternates_are_shown_not_hidden(monkeypatch):
    """Grouping decides what sits under what, not what the table gets to see."""
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "none")
    recorder = Console(force_terminal=False, no_color=True, record=True, width=200)

    choose_proposals(recorder, [SweepProposal(text=text) for text in RAIL])

    output = " ".join(recorder.export_text().split())
    assert "also:" in output and RAIL[1] in output
