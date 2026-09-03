"""P0.5: the D-008 event vocabulary.

These tests exist mostly to pin the *contract*. Phase 7's instruments read this stream,
so a field quietly renamed here is a broken analysis three phases later.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from dndc.schema.events import (
    EVENT_MODELS,
    CallStatus,
    CanonWrite,
    Cost,
    DiceRoll,
    Escalation,
    Event,
    EventType,
    GMAdjudication,
    GMNarration,
    NPCTurn,
    PlayerInput,
    RulesResolution,
    SeatInfo,
    SessionMeta,
)

ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def roll(total: int = 14) -> DiceRoll:
    return DiceRoll(expression="1d20+2", rolls=(12,), kept=(12,), modifier=2, total=total)


def test_every_event_type_has_a_model():
    """D-008 names seventeen families; the map must stay exhaustive."""
    assert set(EVENT_MODELS) == set(EventType)
    assert len(EVENT_MODELS) == 17


def test_the_d008_family_names_are_exactly_as_specified():
    """Pinned so the vocabulary cannot grow in code before it grows in D-008.

    `inventory_change` and `chronicle_write` were added by the 2026-08-09 amendment, the
    four combat families by the 2026-08-15 one, `background_write` by the 2026-09-02 one,
    and `belief_change` by the 2026-09-03 one; this test failing is the intended cost of
    adding a family, not an obstacle to it.
    """
    assert {t.value for t in EventType} == {
        "session_meta",
        "player_input",
        "rules_resolution",
        "gm_adjudication",
        "gm_narration",
        "npc_turn",
        "canon_write",
        "belief_change",
        "inventory_change",
        "chronicle_write",
        "background_write",
        "combat_start",
        "combat_turn",
        "hit_point_change",
        "combat_end",
        "escalation",
        "cost",
    }


def test_a_conflict_write_records_that_canon_was_kept():
    """The contradiction rule: the ledger does not follow the model (Phase 2)."""
    from dndc.schema.events import CanonOperation, CanonWrite

    event = CanonWrite(
        seq=1,
        session_id="s1",
        entry_id="world-ashmill-1",
        scope="world",
        operation=CanonOperation.CONFLICT,
        statement="Ashmill is a town on the salt road.",
        established_by="gm narration (turn 14) called it Kellmoor",
    )
    assert ADAPTER.validate_python(event.model_dump(mode="json")).operation == "conflict"


def test_a_declined_inventory_proposal_is_still_logged():
    from dndc.schema.events import InventoryChange, InventoryDirection

    event = InventoryChange(
        seq=2,
        session_id="s1",
        character="Corin Vale",
        item="coil of rope",
        direction=InventoryDirection.GAIN,
        established_by="[[GAIN: coil of rope]]",
        confirmed=False,
    )
    round_tripped = ADAPTER.validate_python(event.model_dump(mode="json"))
    assert round_tripped.confirmed is False
    assert round_tripped.quantity == 1


def test_a_chronicle_entry_is_not_a_canon_entry():
    """Separate families so a lossy summary cannot enter the ledger as a fact."""
    from dndc.schema.events import ChronicleWrite

    event = ChronicleWrite(
        seq=3,
        session_id="s2",
        covers_sessions=("s1",),
        summary="The party reached Ashmill and searched the chapel.",
        model="llama3.1:8b",
    )
    assert ADAPTER.validate_python(event.model_dump(mode="json")).covers_sessions == ("s1",)


def test_session_meta_carries_the_commit_sha_and_seats():
    event = SessionMeta(
        seq=0,
        session_id="s1",
        dndc_version="0.1.0",
        commit_sha="abc123",
        billing="api",
        seats={"gm": SeatInfo(backend="gmbackend", model="claude-sonnet-5")},
        seed=99,
    )
    assert event.commit_sha == "abc123"
    assert event.seats["gm"].model == "claude-sonnet-5"
    assert event.seed == 99
    assert event.type is EventType.SESSION_META


def test_dirty_worktree_defaults_false_and_is_recordable():
    """A SHA from a dirty tree does not describe the code that ran."""
    assert SessionMeta(seq=0, session_id="s", dndc_version="0", billing="api").dirty_worktree is False
    dirty = SessionMeta(
        seq=0, session_id="s", dndc_version="0", billing="api", dirty_worktree=True
    )
    assert dirty.dirty_worktree is True


def test_rules_resolution_records_individual_faces_not_just_the_total():
    """Reproducibility: a logged session must replay exactly."""
    event = RulesResolution(
        seq=1, session_id="s1", kind="check", dc=15, roll=roll(), seed=4242, success=False
    )
    assert event.roll.rolls == (12,)
    assert event.roll.total == 14
    assert event.dc == 15
    assert event.seed == 4242
    assert event.success is False


def test_adjudication_links_to_the_resolution_it_governed():
    """Ruling fairness is a query over these pairs, not a reading exercise."""
    event = GMAdjudication(
        seq=2,
        session_id="s1",
        situation="Vaulting the fence while pursued",
        ruling="Athletics check",
        dc=13,
        ability="str",
        resolution_seq=1,
    )
    assert event.resolution_seq == 1
    assert event.dc == 13


def test_npc_turn_records_the_gatekeeper_verdict():
    """A blocked draft is still logged — leaks are the object of study (D-003)."""
    event = NPCTurn(
        seq=3,
        session_id="s1",
        npc="miller",
        text="I saw nothing that night.",
        gatekeeper_verdict="blocked",
        gatekeeper_reason="referenced a fact outside knowledge scope",
    )
    assert event.gatekeeper_verdict == "blocked"


def test_canon_write_carries_provenance_and_supersession():
    event = CanonWrite(
        seq=4,
        session_id="s1",
        entry_id="fact-012",
        scope="world_truth",
        statement="The bridge at Aldermoor is out.",
        established_by="session 3, turn 41",
        supersedes="fact-004",
    )
    assert event.scope == "world_truth"
    assert event.supersedes == "fact-004"


def test_escalation_records_the_trigger_and_both_models():
    event = Escalation(
        seq=5,
        session_id="s1",
        trigger="threshold: first confrontation with the Warden",
        from_model="claude-sonnet-5",
        to_model="claude-opus-5",
    )
    assert (event.from_model, event.to_model) == ("claude-sonnet-5", "claude-opus-5")


def test_cost_can_express_would_have_cost_for_subscription_mode():
    """D-004: the billing toggle is only measurable if subscription logs a shadow price."""
    event = Cost(
        seq=6,
        session_id="s1",
        seat="gm",
        model="claude-sonnet-5",
        billing="subscription",
        input_tokens=1200,
        output_tokens=300,
        usd=0.0084,
        would_have_cost=True,
        for_seq=5,
    )
    assert event.would_have_cost is True
    assert event.for_seq == 5


def test_model_calls_can_be_logged_as_pending_before_they_are_made():
    """D-008's pending-state discipline: a crash mid-call stays reconstructable."""
    pending = GMNarration(seq=7, session_id="s1", text="", status=CallStatus.PENDING)
    assert pending.status is CallStatus.PENDING
    assert GMNarration(seq=8, session_id="s1", text="done").status is CallStatus.COMPLETE


def test_call_id_pairs_a_model_call_across_its_writes():
    """OD-9: adjacency pairing breaks under Phase 4's interleaved NPC calls."""
    call = "abc123"
    pending = GMNarration(seq=0, session_id="s", text="", status=CallStatus.PENDING, call_id=call)
    done = GMNarration(seq=1, session_id="s", text="The hall is cold.", call_id=call)
    cost = Cost(seq=2, session_id="s", seat="gm", model="m", billing="api", call_id=call)
    assert pending.call_id == done.call_id == cost.call_id == call


def test_npc_turns_carry_a_call_id_too():
    event = NPCTurn(seq=0, session_id="s", npc="miller", text="Aye.", call_id="xyz")
    assert event.call_id == "xyz"


def test_call_id_is_optional():
    """Deterministic events (rules_resolution, canon_write) have no model call to pair."""
    assert GMNarration(seq=0, session_id="s", text="x").call_id is None


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        PlayerInput(seq=0, session_id="s", player="Kelly", text="hi", mood="curious")


def test_events_are_frozen():
    event = PlayerInput(seq=0, session_id="s", player="Kelly", text="hi")
    with pytest.raises(ValidationError):
        event.text = "changed"


def test_negative_seq_is_rejected():
    with pytest.raises(ValidationError):
        PlayerInput(seq=-1, session_id="s", player="Kelly", text="hi")


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "player_input", "seq": 0, "session_id": "s", "player": "K", "text": "hi"},
        {
            "type": "rules_resolution",
            "seq": 1,
            "session_id": "s",
            "kind": "attack",
            "roll": {"expression": "1d20+5", "total": 18},
        },
        {"type": "gm_narration", "seq": 2, "session_id": "s", "text": "The door creaks."},
        {
            "type": "cost",
            "seq": 3,
            "session_id": "s",
            "seat": "gm",
            "model": "m",
            "billing": "api",
        },
    ],
)
def test_the_union_dispatches_on_type(payload):
    event = ADAPTER.validate_python(payload)
    assert event.type.value == payload["type"]


def test_an_unknown_event_type_is_rejected():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "vibes", "seq": 0, "session_id": "s"})
