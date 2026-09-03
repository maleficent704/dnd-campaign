"""P4.6 — a character changes their mind, and the old belief stops reaching their prompt.

Three properties carry this file:

**A retired belief leaves the prompt, and only the prompt.** It stays in the ledger with a
pointer to what replaced it, because a superseded entry is what drift is measured against.
What must not survive is its presence in the next call.

**The pass runs before anyone speaks.** A guard whose mind the GM just changed, and who is
handed the floor in the same reply, answers from the new mind. Retiring the old belief
after he has spoken means the table hears the contradiction first and the correction a turn
later, which is the whole failure.

**Every fail-open path is visible.** No judge, a dead host, an unparseable verdict — all of
them retire nothing and say so. A pass that ran and retired nothing must never be
indistinguishable from a pass that never ran, which is the same argument that gave the gate
its `unchecked` verdict.
"""

from __future__ import annotations

import pytest

from dndc.game.beliefturn import StanceKeeper
from dndc.game.npcturn import NPCVoice
from dndc.game.turn import TurnEngine
from dndc.gm.belieftag import BELIEF_PATTERN, BeliefTag, find_belief_tags, strip_belief_tags
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, PartyMember
from dndc.gm.stance import (
    StanceCase,
    StanceJudge,
    StanceJudgement,
    render_standing,
    run_stance_control,
)
from dndc.logging import SessionLog, read_log
from dndc.memory.canon_store import CanonStore
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.events import CanonOperation, CanonSource, EventType, StanceStatus
from dndc.schema.npc import NPC, VoiceCard

# --- the tag ---------------------------------------------------------------


def test_a_belief_tag_carries_the_character_and_what_they_now_think():
    found = find_belief_tags(
        "His jaw works.\n[[BELIEF: the caravan guard | the teamster did not take it]]"
    )
    assert [(tag.name, tag.belief) for tag in found] == [
        ("the caravan guard", "the teamster did not take it")
    ]


@pytest.mark.parametrize("separator", ["|", "->", "→", "—", "=>"])
def test_the_separator_is_whatever_the_model_reached_for(separator):
    """Shared with `[[SPEAK]]` through `tagsyntax`, so the two cannot drift apart on one
    en dash and disagree about what a tag says."""
    found = find_belief_tags(f"[[BELIEF: Maren {separator} the reeve was lying]]")
    assert found[0].name == "Maren"
    assert found[0].belief == "the reeve was lying"


def test_a_tag_with_no_belief_in_it_establishes_nothing():
    """Half a tag is a formatting slip, and inventing the missing half would be inventing
    canon. The same call `[[CANON]]` makes on an empty body."""
    assert find_belief_tags("[[BELIEF: Maren]]") == []
    assert find_belief_tags("[[BELIEF: | the reeve was lying]]") == []


def test_the_tag_is_case_insensitive_and_survives_stray_punctuation():
    found = find_belief_tags("[[belief: Maren: | the reeve was lying]]")
    assert found[0].name == "Maren"


def test_two_changes_of_mind_for_one_character_are_both_kept():
    """Unlike `[[SPEAK]]`, where a repeat would have her answer without hearing herself.
    Two changes are just two changes, and collapsing them would silently drop the second
    half of "he stops believing X, and now thinks Y"."""
    found = find_belief_tags(
        "[[BELIEF: Maren | the reeve was lying]] "
        "[[BELIEF: Maren | the boat left before dark]]"
    )
    assert [tag.belief for tag in found] == [
        "the reeve was lying",
        "the boat left before dark",
    ]


def test_tags_are_stripped_before_anyone_sees_the_narration():
    text = "His jaw works.\n\n[[BELIEF: the guard | the teamster is honest]]\n"
    assert strip_belief_tags(text) == "His jaw works."


def test_the_pattern_does_not_swallow_ordinary_prose():
    assert find_belief_tags("Belief: a strong word for it.") == []
    assert BELIEF_PATTERN.search("[[CANON: npc_belief (Maren) — the reeve lied]]") is None


# --- fixtures --------------------------------------------------------------


def guard(**fields) -> NPC:
    defaults = {
        "voice": VoiceCard(role="caravan guard", manner="clipped"),
        "knows_tags": ("caravan",),
    }
    defaults.update(fields)
    return NPC.create("the caravan guard", **defaults)


def belief(entry_id: str, text: str, subject: str = "the caravan guard") -> CanonEntry:
    return CanonEntry(
        id=entry_id, text=text, scope=CanonScope.NPC_BELIEF, subject=subject
    )


@pytest.fixture
def ledger() -> CanonLedger:
    book = CanonLedger()
    book.add(
        CanonEntry(
            id="world-crate",
            text="A crate is missing from the third wagon.",
            scope=CanonScope.WORLD,
            tags=("caravan",),
        )
    )
    book.add(belief("belief-guard-teamster", "The teamster took the crate."))
    book.add(belief("belief-guard-wagon", "The crate went missing from his own wagon."))
    return book


def verdict(retire, reason="", quote="took the crate") -> str:
    """A judge reply in the contract's own shape: a number *and* the contradicted words.

    Every retirement carries a quote because an unquoted one is dropped — that is the
    fail-safe direction, and `test_an_unquoted_retirement_is_dropped` is the test that
    pins it.
    """
    items = ", ".join(
        '{"number": ' + str(number) + ', "contradicts": "' + quote + '"}'
        for number in retire
    )
    return '{"retire": [' + items + '], "reason": "' + reason + '"}'


def bare(retire) -> str:
    """The old shape, with no quote. Kept so the drop is tested rather than assumed."""
    numbers = ", ".join(str(number) for number in retire)
    return '{"retire": [' + numbers + '], "reason": ""}'


def campaign(cast=(), ledger=None) -> CampaignContext:
    return CampaignContext(
        name="The Salt Road",
        scene="The Brakewater crossroads at dusk.",
        party=[PartyMember(name="Corin Vale", player="Kelly")],
        ledger=ledger if ledger is not None else CanonLedger(),
        cast=list(cast),
    )


# --- the judge -------------------------------------------------------------


def test_the_judge_retires_the_beliefs_it_names(ledger):
    standing = [ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")]
    judge = StanceJudge(backend=MockBackend([verdict([1], "he believes the teamster")]))

    judgement = judge.judge("the caravan guard", "The teamster is honest.", standing)

    assert [entry.id for entry in judgement.retired] == ["belief-guard-teamster"]
    assert [entry.id for entry in judgement.kept] == ["belief-guard-wagon"]
    assert judgement.judged


def test_retiring_nothing_is_a_perfectly_good_verdict(ledger):
    standing = [ledger.get("belief-guard-teamster")]
    judge = StanceJudge(backend=MockBackend([verdict([])]))

    judgement = judge.judge("the caravan guard", "The master is back at the wagons.", standing)

    assert judgement.retired == ()
    assert judgement.judged is True


def test_a_number_that_is_not_on_the_list_is_dropped_without_losing_the_ones_that_are(ledger):
    """A judge answering `[2, 7]` against a list of two has got one right, and discarding
    it to punish the 7 would lose a correct retirement to a formatting slip."""
    standing = [ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")]
    judge = StanceJudge(backend=MockBackend([verdict([2, 7, 0, -1])]))

    judgement = judge.judge("the caravan guard", "It was never in his wagon.", standing)

    assert [entry.id for entry in judgement.retired] == ["belief-guard-wagon"]


def test_an_unquoted_retirement_is_dropped(ledger):
    """The quote is the test, not a formality: a judge that cannot point at the words the
    new belief contradicts has retired on relatedness. Dropping it is the fail-safe
    direction — keeping a belief is recoverable, losing one silently is not — and it is
    self-policing, because a judge that stops quoting stops retiring and the control
    notices on the next run.

    Measured 2026-09-03: this is what fixed the teamster's false retirement, where four
    prompt revisions had not.
    """
    standing = [ledger.get("belief-guard-teamster")]
    judge = StanceJudge(backend=MockBackend([bare([1])]))

    judgement = judge.judge("the caravan guard", "The teamster is honest.", standing)

    assert judgement.retired == ()
    assert judgement.judged is True


def test_a_retirement_quoting_nothing_at_all_is_dropped(ledger):
    standing = [ledger.get("belief-guard-teamster")]
    judge = StanceJudge(backend=MockBackend([verdict([1], quote="   ")]))

    assert judge.judge("the caravan guard", "The teamster is honest.", standing).retired == ()


def test_a_character_with_no_standing_beliefs_costs_no_call():
    backend = MockBackend([verdict([1])])
    judge = StanceJudge(backend=backend)

    judgement = judge.judge("the caravan guard", "The teamster is honest.", [])

    assert backend.calls == []
    assert judgement.judged is True
    assert judgement.retired == ()


def test_a_malformed_verdict_is_retried_once(ledger):
    standing = [ledger.get("belief-guard-teamster")]
    backend = MockBackend(["I think number one goes.", verdict([1])], repeat_last=False)
    judge = StanceJudge(backend=backend)

    judgement = judge.judge("the caravan guard", "The teamster is honest.", standing)

    assert len(backend.calls) == 2
    assert [entry.id for entry in judgement.retired] == ["belief-guard-teamster"]


def test_two_malformed_verdicts_retire_nothing_and_say_so(ledger):
    """Fail open. The ledger is left exactly as it was, which is the behaviour every phase
    before this one had — a broken judge costs the improvement, never the campaign."""
    standing = [ledger.get("belief-guard-teamster")]
    judge = StanceJudge(backend=MockBackend(["not json", "still not json"]))

    judgement = judge.judge("the caravan guard", "The teamster is honest.", standing)

    assert judgement.retired == ()
    assert judgement.judged is False
    assert "unparseable" in judgement.reason


def test_a_dead_host_retires_nothing_and_never_raises(ledger):
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("connection refused")

    standing = [ledger.get("belief-guard-teamster")]
    judgement = StanceJudge(backend=Dead()).judge(
        "the caravan guard", "The teamster is honest.", standing
    )

    assert judgement.judged is False
    assert judgement.retired == ()
    assert "connection refused" in judgement.reason


def test_the_judge_is_shown_beliefs_and_nothing_else(ledger):
    """No canon, no `gm_only`, no voice card. A character's own beliefs are already theirs,
    and the plot does not enter a second model call to save a round trip."""
    standing = [ledger.get("belief-guard-teamster")]
    backend = MockBackend([verdict([])])

    StanceJudge(backend=backend).judge(
        "the caravan guard", "The teamster is honest.", standing
    )

    system = backend.calls[0].system
    assert "The teamster took the crate." in system
    assert "A crate is missing from the third wagon." not in system
    assert "caravan guard" in system


def test_the_standing_beliefs_are_numbered_because_the_answer_is_numbers(ledger):
    rendered = render_standing(
        [ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")]
    )
    assert rendered.splitlines()[0].startswith("1. ")
    assert rendered.splitlines()[1].startswith("2. ")


# --- the ledger ------------------------------------------------------------


def test_retiring_points_an_entry_at_one_already_filed(ledger):
    """`supersede` mints a replacement, which is right when the world changes once. One
    change of mind can retire several beliefs, and minting a copy of the same sentence per
    retirement would leave Phase 7 counting one thought as three."""
    ledger.add(belief("belief-guard-honest", "The teamster is honest."))
    before = len(ledger.entries)

    ledger.retire("belief-guard-teamster", "belief-guard-honest")

    assert len(ledger.entries) == before
    assert ledger.get("belief-guard-teamster").superseded_by == "belief-guard-honest"
    assert ledger.get("belief-guard-teamster").active is False


def test_a_retired_belief_stays_on_file_and_leaves_the_prompt(ledger):
    ledger.add(belief("belief-guard-honest", "The teamster is honest."))
    ledger.retire("belief-guard-teamster", "belief-guard-honest")

    scoped = {entry.id for entry in ledger.for_npc(guard())}
    assert "belief-guard-teamster" not in scoped
    assert "belief-guard-honest" in scoped
    assert ledger.get("belief-guard-teamster") is not None


def test_a_belief_cannot_be_retired_twice_or_by_itself(ledger):
    ledger.add(belief("belief-guard-honest", "The teamster is honest."))
    ledger.retire("belief-guard-teamster", "belief-guard-honest")

    with pytest.raises(ValueError):
        ledger.retire("belief-guard-teamster", "belief-guard-honest")
    with pytest.raises(ValueError):
        ledger.retire("belief-guard-honest", "belief-guard-honest")
    with pytest.raises(KeyError):
        ledger.retire("belief-guard-wagon", "belief-nobody")


def test_a_retirement_is_logged_as_a_supersession_by_the_stance_pass(tmp_path, ledger):
    """`source` is the measurement: a row that took a belief out of circulation was decided
    by a second call on a different seat, and "how much did the judge retire?" is not
    answerable if it looks like the GM's own."""
    log = SessionLog.open(tmp_path)
    store = CanonStore(ledger, log=log)
    replacement = store.establish(
        "The teamster is honest.", scope=CanonScope.NPC_BELIEF, subject="the caravan guard"
    )

    store.retire("belief-guard-teamster", replacement, established_by="[[BELIEF: ...]]")

    rows = [
        event
        for event in read_log(log.path)
        if event.type is EventType.CANON_WRITE
        and event.operation is CanonOperation.SUPERSEDE
    ]
    assert len(rows) == 1
    assert rows[0].supersedes == "belief-guard-teamster"
    assert rows[0].source is CanonSource.STANCE


# --- applying a change of mind ---------------------------------------------


def test_applying_a_tag_files_the_belief_and_retires_what_it_replaces(ledger):
    store = CanonStore(ledger)
    keeper = StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([1])])))

    update = keeper.apply(
        guard(), BeliefTag(name="the caravan guard", belief="The teamster is honest."), store
    )

    assert update.entry is not None
    assert update.entry.scope is CanonScope.NPC_BELIEF
    assert update.entry.subject == "the caravan guard"
    assert [entry.id for entry in update.retired] == ["belief-guard-teamster"]
    assert ledger.get("belief-guard-teamster").active is False


def test_with_no_judge_the_belief_is_still_filed_and_nothing_is_retired(ledger):
    """What an ungated or judge-less session gets: the GM can still change a character's
    mind, nothing is retired, and the row says `unjudged` rather than pretending."""
    store = CanonStore(ledger)
    keeper = StanceKeeper()

    update = keeper.apply(
        guard(), BeliefTag(name="the caravan guard", belief="The teamster is honest."), store
    )

    assert update.entry is not None
    assert update.retired == ()
    assert update.judged is False


def test_a_change_of_mind_never_reaches_another_characters_beliefs(ledger):
    """`for_npc` already refuses to hand one character another's, and a change of mind must
    not reach across and retire a belief that is not this character's to abandon."""
    ledger.add(belief("belief-master-honest", "The teamster is a good hand.", subject="the caravan master"))
    store = CanonStore(ledger)
    backend = MockBackend([verdict([])])
    keeper = StanceKeeper(judge=StanceJudge(backend=backend))

    keeper.apply(
        guard(), BeliefTag(name="the caravan guard", belief="The teamster is honest."), store
    )

    system = backend.calls[0].system
    assert "The teamster is a good hand." not in system
    assert "The teamster took the crate." in system


def test_a_restated_belief_establishes_nothing_and_retires_nothing(ledger):
    """`establish` suppresses a fact the ledger already holds word for word, so there is no
    new entry for the old ones to point at. The pass declines rather than retiring against
    an entry the caller never saw."""
    store = CanonStore(ledger)
    keeper = StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([2])])))

    update = keeper.apply(
        guard(),
        BeliefTag(name="the caravan guard", belief="The teamster took the crate."),
        store,
    )

    assert update.entry is None
    assert update.retired == ()
    assert ledger.get("belief-guard-wagon").active is True


def test_the_pass_is_logged_with_what_it_saw_and_what_it_took(tmp_path, ledger):
    """`considered` minus `retired` is what the judge left standing — the only way to tell
    a conservative judge from an absent one."""
    log = SessionLog.open(tmp_path)
    store = CanonStore(ledger, log=log)
    keeper = StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([1], "he believes him")])), log=log)

    keeper.apply(
        guard(),
        BeliefTag(
            name="the caravan guard",
            belief="The teamster is honest.",
            raw="[[BELIEF: the caravan guard | The teamster is honest.]]",
        ),
        store,
        turn=4,
    )

    rows = [e for e in read_log(log.path) if e.type is EventType.BELIEF_CHANGE]
    assert len(rows) == 1
    row = rows[0]
    assert row.npc == "the caravan guard"
    assert row.belief == "The teamster is honest."
    assert row.considered == "belief-guard-teamster,belief-guard-wagon"
    assert row.retired == "belief-guard-teamster"
    assert row.status is StanceStatus.JUDGED
    assert row.turn_seq == 4
    assert row.established_by.startswith("[[BELIEF:")


def test_a_pass_that_could_not_run_is_logged_as_unjudged(tmp_path, ledger):
    """The fail-open row. A night where the judge was down must not read, later, as a night
    where nothing needed retiring."""
    log = SessionLog.open(tmp_path)
    store = CanonStore(ledger, log=log)
    keeper = StanceKeeper(judge=StanceJudge(backend=MockBackend(["not json", "nor this"])), log=log)

    keeper.apply(
        guard(), BeliefTag(name="the caravan guard", belief="The teamster is honest."), store
    )

    row = [e for e in read_log(log.path) if e.type is EventType.BELIEF_CHANGE][0]
    assert row.status is StanceStatus.UNJUDGED
    assert row.retired is None
    assert row.considered == "belief-guard-teamster,belief-guard-wagon"


def test_the_judge_call_is_billed_with_its_latency(tmp_path, ledger):
    """The gate does not do this and probably should. (g) was caught quoting a latency from
    memory that the log could not confirm; this one is on the critical path of a turn."""
    log = SessionLog.open(tmp_path)
    store = CanonStore(ledger, log=log)
    keeper = StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([])])), log=log)

    keeper.apply(
        guard(), BeliefTag(name="the caravan guard", belief="The master is back."), store
    )

    costs = [e for e in read_log(log.path) if e.type is EventType.COST]
    assert len(costs) == 1
    assert costs[0].seat == "utility_batch"


# --- in the turn -----------------------------------------------------------


def test_the_gm_can_change_a_characters_mind_mid_turn(ledger):
    scene = campaign(cast=[guard()], ledger=ledger)
    engine = TurnEngine(
        backend=MockBackend(
            ["His jaw works. [[BELIEF: the caravan guard | The teamster is honest.]]"]
        ),
        campaign=scene,
        stance=StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([1])]))),
    )

    result = engine.run("I lay out what I saw", player="Kelly")

    assert [update.belief for update in result.beliefs] == ["The teamster is honest."]
    assert [entry.id for entry in result.beliefs[0].retired] == ["belief-guard-teamster"]
    assert "BELIEF" not in result.narration


def test_a_change_of_mind_for_somebody_who_does_not_exist_is_surfaced(ledger):
    """Worse than an unvoiced direction, and the one failure here that leaves no row
    anywhere else: the GM thinks it has moved the world and will keep narrating from a
    belief nobody holds."""
    scene = campaign(cast=[guard()], ledger=ledger)
    engine = TurnEngine(
        backend=MockBackend(["[[BELIEF: the harbourmaster | the fee is fair]]"]),
        campaign=scene,
        stance=StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([1])]))),
    )

    result = engine.run("I argue the fee", player="Kelly")

    assert [tag.name for tag in result.unchanged] == ["the harbourmaster"]
    assert result.beliefs == []
    assert ledger.get("belief-guard-teamster").active is True


def test_the_mind_changes_before_the_character_speaks(ledger):
    """The load-bearing ordering. A guard turned around in the same reply that hands him
    the floor must answer from the new mind — retiring the old belief after he has spoken
    means the table hears the contradiction first and the correction a turn later."""
    scene = campaign(cast=[guard()], ledger=ledger)
    voice = NPCVoice(backend=MockBackend(["I was wrong about him."]))
    engine = TurnEngine(
        backend=MockBackend(
            [
                "His jaw works. "
                "[[BELIEF: the caravan guard | The teamster is honest.]] "
                "[[SPEAK: the caravan guard | asked what he thinks now]]"
            ]
        ),
        campaign=scene,
        voice=voice,
        stance=StanceKeeper(judge=StanceJudge(backend=MockBackend([verdict([1])]))),
    )

    engine.run("I lay out what I saw", player="Kelly")

    npc_call = voice.backend.calls[-1]
    assert "The teamster is honest." in npc_call.system
    assert "The teamster took the crate." not in npc_call.system


def test_a_turn_without_a_tag_costs_no_judge_call(ledger):
    scene = campaign(cast=[guard()], ledger=ledger)
    judge_backend = MockBackend([verdict([1])])
    engine = TurnEngine(
        backend=MockBackend(["He does not move."]),
        campaign=scene,
        stance=StanceKeeper(judge=StanceJudge(backend=judge_backend)),
    )

    engine.run("I wait", player="Kelly")

    assert judge_backend.calls == []
    assert engine.campaign.ledger.get("belief-guard-teamster").active is True


# --- the positive control --------------------------------------------------


def test_the_control_scores_recall_and_retirements_in_error(ledger):
    """The P2.6 rule where it is easiest to break: this pass fails open, so "nothing was
    retired" is what a correct judge, a wrong one, and a dead host all look like."""
    standing = [ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")]
    cases = [
        StanceCase(
            belief="The teamster is honest.",
            retires=("The teamster took the crate.",),
        ),
        StanceCase(belief="The master is back at the wagons."),
    ]
    # First case: retires the right one. Second: retires one it should have left alone.
    judge = StanceJudge(
        backend=MockBackend([verdict([1]), verdict([2])], repeat_last=False)
    )

    report = run_stance_control(judge, "the caravan guard", standing, cases)

    assert report.retired == 1
    assert report.should_retire == 1
    assert report.false_retirements == 1
    assert report.trustworthy is False
    assert "retired 1/1" in report.summary()


def test_a_control_run_the_judge_could_not_answer_is_not_a_pass(ledger):
    standing = [ledger.get("belief-guard-teamster")]
    cases = [StanceCase(belief="The master is back at the wagons.")]
    judge = StanceJudge(backend=MockBackend(["not json", "nor this"]))

    report = run_stance_control(judge, "the caravan guard", standing, cases)

    assert report.unjudged == 1
    assert report.false_retirements == 0
    assert report.trustworthy is False


def test_a_clean_run_is_trustworthy(ledger):
    standing = [ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")]
    cases = [
        StanceCase(
            belief="The teamster is honest.", retires=("The teamster took the crate.",)
        )
    ]
    judge = StanceJudge(backend=MockBackend([verdict([1])]))

    report = run_stance_control(judge, "the caravan guard", standing, cases)

    assert report.trustworthy is True
    assert report.kept == 1
    assert report.false_retirements == 0


def test_a_judgement_knows_what_it_left_standing(ledger):
    judgement = StanceJudgement(
        retired=(ledger.get("belief-guard-teamster"),),
        considered=(ledger.get("belief-guard-teamster"), ledger.get("belief-guard-wagon")),
    )
    assert [entry.id for entry in judgement.kept] == ["belief-guard-wagon"]
