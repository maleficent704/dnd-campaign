"""P4.4: the NPC output gate — a backstop, and what happens when it breaks.

Offline. The checker is a `MockBackend` replaying verdicts, so the paths that matter — a
malformed reply, a dead host, a demand for a rewrite that never comes — are three lines
each instead of an afternoon of breaking things on purpose.
"""

from __future__ import annotations

import pytest

from dndc.game.npcturn import NPCVoice
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.gatekeeper import ControlCase, Gatekeeper, Verdict, run_control
from dndc.logging import SessionLog, read_log
from dndc.models.mock import MockBackend
from dndc.schema.events import EventType
from dndc.schema.npc import NPC, VoiceCard

CLEAN = '{"verdict": "pass", "reason": "", "rewrite": null}'
REVISE = (
    '{"verdict": "revise", "reason": "invents the Marlow brothers", '
    '"rewrite": "Some have stopped landing. Couldn\'t tell you why."}'
)
NO_REWRITE = '{"verdict": "revise", "reason": "invents a name", "rewrite": null}'


@pytest.fixture
def ledger() -> CanonLedger:
    book = CanonLedger()
    book.add(CanonEntry(id="w1", text="The harbourmaster takes a cut.", tags=("harbour",)))
    book.add(CanonEntry(id="b1", text="Maren thinks he is merely greedy.",
                        scope=CanonScope.NPC_BELIEF, subject="Maren", tags=("harbour",)))
    book.add(CanonEntry(id="g1", text="He is the smuggling ring's paymaster.",
                        scope=CanonScope.GM_ONLY, tags=("harbour",)))
    return book


def maren() -> NPC:
    return NPC.create("Maren", knows_tags=("harbour",), voice=VoiceCard(role="innkeeper"))


def gate(*verdicts: str) -> Gatekeeper:
    return Gatekeeper(backend=MockBackend(responses=list(verdicts), repeat_last=False))


# --- verdicts --------------------------------------------------------------


def test_a_clean_draft_passes_through_unchanged(ledger):
    judgement = gate(CLEAN).check(maren(), ledger, "He takes his cut, always has.")
    assert judgement.verdict is Verdict.PASS
    assert judgement.text == "He takes his cut, always has."
    assert judgement.intercepted is False


def test_an_invention_is_replaced_by_the_rewrite(ledger):
    judgement = gate(REVISE).check(maren(), ledger, "The Marlow brothers stopped landing.")
    assert judgement.verdict is Verdict.REVISED
    assert judgement.text.startswith("Some have stopped landing")
    assert judgement.draft == "The Marlow brothers stopped landing."
    assert judgement.intercepted is True


def test_a_demanded_repair_with_no_rewrite_blocks(ledger):
    """The conservative reading: it found something and could not fix it, so showing the
    draft anyway would make the interception meaningless."""
    judgement = gate(NO_REWRITE).check(maren(), ledger, "Old Tam saw the boat.")
    assert judgement.verdict is Verdict.BLOCKED
    assert judgement.text == ""
    assert judgement.draft == "Old Tam saw the boat."


def test_the_raw_draft_survives_every_verdict(ledger):
    """Pre-censor drafts are the denominator of every leak rate Phase 7 will compute."""
    for verdict in (CLEAN, REVISE, NO_REWRITE):
        judgement = gate(verdict).check(maren(), ledger, "the draft")
        assert judgement.draft == "the draft"


def test_an_empty_draft_is_not_a_gate_failure(ledger):
    judgement = gate().check(maren(), ledger, "   ")
    assert judgement.verdict is Verdict.PASS
    assert judgement.text == ""


# --- failing open ----------------------------------------------------------


def test_a_dead_checker_shows_the_draft_and_says_it_was_unchecked(ledger):
    """A backstop that can halt play is worse than no backstop."""
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise RuntimeError("could not reach Ollama")

    judgement = Gatekeeper(backend=Dead()).check(maren(), ledger, "He takes his cut.")
    assert judgement.verdict is Verdict.UNCHECKED
    assert judgement.text == "He takes his cut."
    assert "could not reach Ollama" in judgement.reason


def test_unparseable_output_is_retried_once_then_fails_open(ledger):
    judgement = gate("not json at all", "still not json").check(maren(), ledger, "a line")
    assert judgement.verdict is Verdict.UNCHECKED
    assert judgement.text == "a line"
    assert len(judgement.raw) == 2


def test_a_retry_that_lands_is_honoured(ledger):
    judgement = gate("sorry, here you go:", REVISE).check(maren(), ledger, "a line")
    assert judgement.verdict is Verdict.REVISED


def test_a_fenced_verdict_is_read(ledger):
    """Local models fence JSON whatever the prompt says."""
    fenced = "```json\n" + CLEAN + "\n```"
    assert gate(fenced).check(maren(), ledger, "a line").verdict is Verdict.PASS


def test_unchecked_is_never_recorded_as_pass(ledger):
    """The whole argument for the fourth verdict: a night where the checker was down must
    not read, later, as a night with no leaks."""
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise RuntimeError("down")

    assert Gatekeeper(backend=Dead()).check(maren(), ledger, "x").verdict is not Verdict.PASS


# --- what the checker is shown ---------------------------------------------


def test_the_checker_is_judged_against_the_same_list_the_npc_had(ledger):
    """If these diverge the gate becomes noise — it would flag legitimate lines and miss
    invented ones."""
    backend = MockBackend(responses=[CLEAN])
    Gatekeeper(backend=backend).check(maren(), ledger, "a line")
    system = backend.calls[-1].system
    assert "The harbourmaster takes a cut." in system
    assert "Maren thinks he is merely greedy." in system


def test_the_checker_is_never_told_the_secret_either(ledger):
    """Where this departs from the mystery, deliberately: the NPC prompt never held the
    secret, so a leak can only be invention — and asking about invention catches it without
    the plot ever entering a second model call."""
    backend = MockBackend(responses=[CLEAN])
    Gatekeeper(backend=backend).check(maren(), ledger, "a line")
    assert "paymaster" not in backend.calls[-1].full_system
    assert "smuggling" not in backend.calls[-1].full_system


def test_a_belief_is_marked_as_a_belief_for_the_checker(ledger):
    """Otherwise the gate rewrites every honest expression of a wrong opinion."""
    backend = MockBackend(responses=[CLEAN])
    Gatekeeper(backend=backend).check(maren(), ledger, "a line")
    assert "their own belief" in backend.calls[-1].system


# --- wired into the turn ---------------------------------------------------


def test_the_turn_shows_the_rewrite_and_logs_both(ledger, tmp_path):
    log = SessionLog.open(tmp_path)
    voice = NPCVoice(
        backend=MockBackend(responses=["The Marlow brothers stopped landing."]),
        log=log,
        gate=gate(REVISE),
    )
    reply = voice.speak(maren(), ledger, "They ask about the boats.")

    assert reply.text.startswith("Some have stopped landing")
    assert reply.draft == "The Marlow brothers stopped landing."

    turn = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN][-1]
    assert turn.gatekeeper_verdict == "revised"
    assert turn.draft == "The Marlow brothers stopped landing."
    assert turn.text.startswith("Some have stopped landing")


def test_a_clean_line_logs_no_duplicate_draft(ledger, tmp_path):
    """Only on divergence: a copy of every clean line doubles the log to say nothing."""
    log = SessionLog.open(tmp_path)
    NPCVoice(backend=MockBackend(responses=["He takes his cut."]), log=log, gate=gate(CLEAN)).speak(
        maren(), ledger, "?"
    )
    turn = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN][-1]
    assert turn.gatekeeper_verdict == "pass"
    assert turn.draft is None


def test_the_claims_ledger_remembers_what_was_said_not_what_was_drafted(ledger):
    """A character held to a line the table never heard would contradict herself out loud
    to stay consistent with a sentence that was struck before it left her mouth."""
    npc_backend = MockBackend(responses=["The Marlow brothers stopped landing.", "As I said."])
    voice = NPCVoice(backend=npc_backend, gate=gate(REVISE, CLEAN))
    npc = maren()
    voice.speak(npc, ledger, "?")
    voice.speak(npc, ledger, "?")

    volatile = npc_backend.calls[-1].system_volatile
    assert "Some have stopped landing" in volatile
    assert "Marlow" not in volatile


def test_an_ungated_turn_records_no_verdict(ledger, tmp_path):
    log = SessionLog.open(tmp_path)
    NPCVoice(backend=MockBackend(responses=["He takes his cut."]), log=log).speak(
        maren(), ledger, "?"
    )
    turn = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN][-1]
    assert turn.gatekeeper_verdict is None


# --- the positive control --------------------------------------------------


CASES = (
    ControlCase(draft="Old Tam saw the boat at midnight.", invents=True),
    ControlCase(draft="Couldn't tell you.", invents=False),
)


def test_the_control_scores_recall_and_false_positives(ledger):
    report = run_control(gate(REVISE, CLEAN), maren(), ledger, CASES)
    assert (report.caught, report.planted) == (1, 1)
    assert (report.false_positives, report.clean) == (0, 1)
    assert report.trustworthy


def test_a_gate_that_misses_a_planted_leak_is_not_trustworthy(ledger):
    report = run_control(gate(CLEAN, CLEAN), maren(), ledger, CASES)
    assert report.caught == 0
    assert report.misses[0].draft.startswith("Old Tam")
    assert not report.trustworthy


def test_a_gate_that_rewrites_everything_is_not_trustworthy_either(ledger):
    """A gate that flags clean lines protects nothing and ruins every voice in the game."""
    report = run_control(gate(REVISE, REVISE), maren(), ledger, CASES)
    assert report.caught == 1
    assert report.false_positives == 1
    assert not report.trustworthy


def test_a_dead_checker_scores_as_untrustworthy_rather_than_perfect(ledger):
    """Fail-open is right for play and must never look like success in a control run."""
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise RuntimeError("down")

    report = run_control(Gatekeeper(backend=Dead()), maren(), ledger, CASES)
    assert report.caught == 0
    assert not report.trustworthy
