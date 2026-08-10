"""P2.1/P2.2 — the `[[CANON:]]` tag, the store, and canon surviving the process.

Three things are actually being defended here:

* **A fact is never lost to formatting.** The parser's fallbacks matter more than its
  precision; a fact filed under the wrong scope is recoverable, a dropped one is not.
* **The ledger does not follow the model.** Contradiction is logged, canon is kept. This
  is the ratified rule (2026-08-10) and the reason drift is measurable at all.
* **The world survives the process.** A ledger that only exists in memory is the Phase 1
  behaviour Phase 2 exists to end.
"""

from __future__ import annotations

import random

import pytest

from dndc.game.turn import TurnEngine
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.canontag import CANON_PATTERN, find_canon_tags, strip_canon_tags
from dndc.gm.context import CampaignContext, PartyMember
from dndc.logging import SessionLog, read_log
from dndc.memory.canon_store import CANON_FILENAME, CanonStore, normalise
from dndc.models.mock import MockBackend
from dndc.schema.events import CanonOperation, EventType

# --- the tag ---------------------------------------------------------------


def test_a_bare_tag_is_a_world_fact():
    """The common case has no scope word at all, and must still parse."""
    tags = find_canon_tags("[[CANON: The bridge at Aldermoor is out.]]")
    assert len(tags) == 1
    assert tags[0].scope is CanonScope.WORLD
    assert tags[0].text == "The bridge at Aldermoor is out."


@pytest.mark.parametrize(
    "text,scope,subject",
    [
        ("[[CANON: world — Ashmill sits on the salt road.]]", CanonScope.WORLD, None),
        ("[[CANON: gm_only — The reeve took the bribe.]]", CanonScope.GM_ONLY, None),
        ("[[CANON: gm only - The reeve took the bribe.]]", CanonScope.GM_ONLY, None),
        ("[[CANON: GM_ONLY: The reeve took the bribe.]]", CanonScope.GM_ONLY, None),
        ("[[CANON: npc_belief (Miller) — The road is safe.]]", CanonScope.NPC_BELIEF, "Miller"),
        ("[[CANON: player_known — The gate is barred.]]", CanonScope.PLAYER_KNOWN, None),
        ("[[CANON: character (Corin Vale) — He keeps his father's knife.]]", CanonScope.CHARACTER, "Corin Vale"),
    ],
)
def test_scopes_and_subjects_parse(text, scope, subject):
    tag = find_canon_tags(text)[0]
    assert (tag.scope, tag.subject) == (scope, subject)


def test_an_unknown_leading_word_becomes_part_of_the_statement():
    """The opposite posture to `[[CHECK]]`, and deliberately so.

    A missing DC means the GM never made the ruling, so guessing one invents the
    adjudication the log exists to audit. Here the fallback *is* the common case, and
    dropping the fact would be the larger error.
    """
    tag = find_canon_tags("[[CANON: rumour — the mill burned last winter]]")[0]
    assert tag.scope is CanonScope.WORLD
    assert tag.text == "rumour — the mill burned last winter"


def test_a_statement_containing_a_dash_survives():
    tag = find_canon_tags("[[CANON: The reeve — a heavy, unhurried man — keeps the keys.]]")[0]
    assert tag.text == "The reeve — a heavy, unhurried man — keeps the keys."


def test_an_empty_tag_is_not_a_fact():
    assert find_canon_tags("[[CANON: ]] [[CANON: world — ]]") == []


def test_two_tags_in_one_reply_parse_as_two():
    """Non-greedy body: a greedy one would swallow both into a single malformed fact."""
    tags = find_canon_tags("[[CANON: One.]] prose [[CANON: gm_only — Two.]]")
    assert [t.text for t in tags] == ["One.", "Two."]


def test_stripping_removes_the_tags_and_tidies_the_prose():
    text = "He nods.\n\n[[CANON: The gate is barred.]]\n\nBeyond, the road bends."
    assert strip_canon_tags(text) == "He nods.\n\nBeyond, the road bends."


def test_the_scope_alternatives_are_generated_from_the_enum():
    """A new scope must not be parseable in one place and unknown in the other."""
    for scope in CanonScope:
        tag = find_canon_tags(f"[[CANON: {scope.value} — a fact]]")[0]
        assert tag.scope is scope


def test_the_tag_marker_is_the_one_the_stream_filter_hides():
    """The `[[`-suppressing filter is what keeps tags off the players' screens."""
    assert CANON_PATTERN.pattern.startswith(r"\[\[")


# --- the store -------------------------------------------------------------


def store(tmp_path=None, log=None, **kwargs) -> CanonStore:
    path = (tmp_path / CANON_FILENAME) if tmp_path is not None else None
    return CanonStore(CanonLedger(), path=path, log=log, **kwargs)


def test_establishing_a_fact_writes_it_to_disk_immediately(tmp_path):
    """Not at session end: a crash at turn 40 must not cost forty turns of world."""
    subject = store(tmp_path)
    subject.establish("Ashmill sits on the salt road.")

    reloaded = CanonLedger.load(tmp_path / CANON_FILENAME)
    assert [entry.text for entry in reloaded.active()] == ["Ashmill sits on the salt road."]


def test_a_restatement_establishes_nothing(tmp_path):
    """The GM names the town every other turn; the ledger must not grow every time."""
    subject = store(tmp_path)
    first = subject.establish("Ashmill sits on the salt road.")
    again = subject.establish("  ashmill sits on the SALT ROAD  ")

    assert first is not None
    assert again is None
    assert len(subject.ledger) == 1


def test_a_restatement_emits_no_event(tmp_path):
    """Suppression has to be silent in the log too, or Phase 7 counts restatements as
    establishment and every campaign looks maximally generative."""
    log = SessionLog.open(tmp_path)
    subject = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME, log=log)
    subject.establish("The gate is barred.")
    subject.establish("The gate is barred.")

    writes = [e for e in read_log(log.path) if e.type is EventType.CANON_WRITE]
    assert len(writes) == 1


def test_the_same_sentence_in_two_scopes_is_two_facts(tmp_path):
    """A world truth and an NPC's belief are different claims about the world."""
    subject = store(tmp_path)
    subject.establish("The road is safe after dark.", scope=CanonScope.WORLD)
    second = subject.establish(
        "The road is safe after dark.", scope=CanonScope.NPC_BELIEF, subject="Miller"
    )
    assert second is not None
    assert len(subject.ledger) == 2


def test_provenance_is_recorded_on_the_entry_and_the_event(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME, log=log)
    entry = subject.establish(
        "The mill burned last winter.",
        session="s1",
        turn=14,
        established_by="[[CANON: The mill burned last winter.]]",
    )

    assert (entry.session, entry.turn) == ("s1", 14)
    write = next(e for e in read_log(log.path) if e.type is EventType.CANON_WRITE)
    assert write.operation is CanonOperation.CREATE
    assert write.established_by == "[[CANON: The mill burned last winter.]]"
    assert write.scope == "world"


def test_a_conflict_keeps_canon_and_changes_nothing(tmp_path):
    """The ratified contradiction rule. A ledger that follows the latest narration has
    agreed with the drift by definition, and has nothing left to measure against."""
    log = SessionLog.open(tmp_path)
    subject = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME, log=log)
    entry = subject.establish("Ashmill is a town on the salt road.")

    subject.note_conflict(entry.id, "gm narration (turn 14) called it Kellmoor")

    assert [e.text for e in subject.ledger.active()] == ["Ashmill is a town on the salt road."]
    write = [e for e in read_log(log.path) if e.type is EventType.CANON_WRITE][-1]
    assert write.operation is CanonOperation.CONFLICT
    assert write.entry_id == entry.id
    # Both halves: what canon still says, and what disagreed with it.
    assert write.statement == "Ashmill is a town on the salt road."
    assert write.established_by == "gm narration (turn 14) called it Kellmoor"


def test_conflicting_with_an_unknown_entry_raises(tmp_path):
    with pytest.raises(KeyError):
        store(tmp_path).note_conflict("world-nothing", "…")


def test_supersession_keeps_the_old_entry_on_file_and_out_of_the_prompt(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME, log=log)
    old = subject.establish("The bridge at Aldermoor stands.")
    new = subject.supersede(old.id, "The bridge at Aldermoor is out.")

    assert [e.text for e in subject.ledger.active()] == ["The bridge at Aldermoor is out."]
    assert subject.ledger.get(old.id).superseded_by == new.id
    write = [e for e in read_log(log.path) if e.type is EventType.CANON_WRITE][-1]
    assert (write.operation, write.supersedes) == (CanonOperation.SUPERSEDE, old.id)


def test_supersession_inherits_scope_and_subject(tmp_path):
    subject = store(tmp_path)
    old = subject.establish(
        "The road is safe.", scope=CanonScope.NPC_BELIEF, subject="Miller"
    )
    new = subject.supersede(old.id, "The road is not safe.")
    assert (new.scope, new.subject) == (CanonScope.NPC_BELIEF, "Miller")


def test_superseding_an_unknown_entry_raises(tmp_path):
    with pytest.raises(KeyError):
        store(tmp_path).supersede("world-nothing", "…")


def test_a_store_with_no_path_still_logs(tmp_path):
    """A scratch session has nowhere durable to file canon; that is not an error."""
    log = SessionLog.open(tmp_path)
    subject = CanonStore(CanonLedger(), path=None, log=log)
    assert subject.establish("A fact.") is not None
    assert subject.save() is None
    assert [e for e in read_log(log.path) if e.type is EventType.CANON_WRITE]


def test_for_campaign_reads_an_existing_ledger(tmp_path):
    CanonLedger(entries=[CanonEntry(id="world-one", text="One.")]).save(
        tmp_path / CANON_FILENAME
    )
    subject = CanonStore.for_campaign(tmp_path)
    assert [e.text for e in subject.ledger.active()] == ["One."]


def test_a_half_written_save_cannot_replace_a_whole_ledger(tmp_path, monkeypatch):
    """Atomic replace: losing the newest fact is recoverable, losing the campaign is not."""
    subject = store(tmp_path)
    subject.establish("One.")

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("dndc.memory.canon_store.os.replace", explode)
    with pytest.raises(OSError):
        subject.establish("Two.")

    assert CanonLedger.load(tmp_path / CANON_FILENAME).entries[0].text == "One."


def test_normalise_ignores_case_spacing_and_a_trailing_stop():
    assert normalise("The  gate   is barred.") == normalise("the gate is barred")


# --- through the turn loop -------------------------------------------------


def engine_with(responses, tmp_path=None, log=None) -> TurnEngine:
    campaign = CampaignContext(name="The Salt Road", party=[PartyMember(name="Brannoc", player="Kelly")])
    canon = CanonStore(
        CanonLedger(),
        path=(tmp_path / CANON_FILENAME) if tmp_path else None,
        log=log,
    )
    return TurnEngine(
        backend=MockBackend(responses=responses),
        campaign=campaign,
        rng=random.Random(1),
        log=log,
        canon=canon,
    )


def test_a_tagged_fact_reaches_the_ledger_and_the_next_prompt(tmp_path):
    """The whole point: what the GM establishes is in the prompt it gets next turn."""
    engine = engine_with(
        ["The gate is barred. [[CANON: The gate at Ashmill is barred at dusk.]]", "He waits."],
        tmp_path,
    )
    engine.run("I try the gate.", player="Kelly")
    engine.run("I wait.", player="Kelly")

    assert "barred at dusk" in engine.backend.calls[-1].system_volatile


def test_the_tag_never_reaches_the_player_or_the_recent_window():
    """A tag left in the window comes back as the GM's own past voice."""
    engine = engine_with(["He nods. [[CANON: The gate is barred.]] The road bends."])
    result = engine.run("I look around.", player="Kelly")

    assert "[[CANON" not in result.narration
    assert result.narration == "He nods. The road bends."
    assert "[[CANON" not in engine.campaign.history[-1].narration


def test_facts_from_both_calls_of_one_turn_are_kept():
    """A turn that asks for a check narrates twice; the second half establishes too."""
    engine = engine_with(
        [
            "[[CANON: The lock is old iron.]] [[CHECK: Dexterity DC 12 — it sticks]]",
            "It gives. [[CANON: The undercroft floods at high tide.]]",
        ]
    )
    result = engine.run("I pick the lock.", player="Kelly")
    assert [e.text for e in result.canon] == [
        "The lock is old iron.",
        "The undercroft floods at high tide.",
    ]


def test_the_opening_scene_can_establish_canon():
    engine = engine_with(["You stand at the waystation. [[CANON: The waystation is roofless.]]"])
    result = engine.open_scene()
    assert [e.text for e in result.canon] == ["The waystation is roofless."]


def test_the_turn_number_is_recorded_on_the_fact():
    engine = engine_with(["Fine. [[CANON: A fact.]]", "Also. [[CANON: Another fact.]]"])
    engine.run("one", player="Kelly")
    second = engine.run("two", player="Kelly")
    assert second.canon[0].turn == 2


def test_a_refusal_establishes_nothing():
    """A declined turn is not the GM's judgment about the world."""
    from dndc.models.base import GMResponse

    engine = engine_with(
        [GMResponse(text="[[CANON: A fact.]]", model="mock-model", refused=True)]
    )
    result = engine.run("…", player="Kelly")
    assert result.canon == []
    assert len(engine.campaign.ledger) == 0


def test_the_engine_and_the_prompt_share_one_ledger(tmp_path):
    """Rebinding is the guard: a store over a *different* ledger would file facts to disk
    that never reach the prompt — durable, invisible, and impossible to notice in play."""
    campaign = CampaignContext(name="X")
    other = CanonStore(CanonLedger(), path=tmp_path / CANON_FILENAME)
    engine = TurnEngine(backend=MockBackend(), campaign=campaign, canon=other)
    assert engine.campaign.ledger is other.ledger


def test_canon_survives_the_process(tmp_path):
    """Phase 1's known issue, closed: a second session opens with the first one's world."""
    first = engine_with(["Right. [[CANON: The reeve's name is Halda Orrin.]]"], tmp_path)
    first.run("Who runs this place?", player="Kelly")

    second = TurnEngine(
        backend=MockBackend(responses=["…"]),
        campaign=CampaignContext(name="The Salt Road"),
        canon=CanonStore.for_campaign(tmp_path),
    )
    second.run("Remind me who runs this place.", player="Kelly")
    assert "Halda Orrin" in second.backend.calls[-1].system_volatile
