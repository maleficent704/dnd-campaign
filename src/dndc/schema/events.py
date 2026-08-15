"""The D-008 event vocabulary, typed.

Every event the engine emits is one of these nine families. The vocabulary is
specified in `docs/DESIGN-DECISIONS.md` D-008 and extended *there first*, then here —
Phase 7's instruments (canon-drift measurement, ruling-fairness analysis,
cost-per-session) read this stream, so an ad-hoc field invented in code is a silently
broken instrument later.

Two properties the research side depends on:

* **Reproducibility.** `rules_resolution` carries the seed, the expression, and every
  individual die face — not just the total. A logged session replays exactly.
* **Auditability.** `gm_adjudication` carries the DC the GM set *and* the id of the
  `rules_resolution` it governed, so "was the GM fair?" is a query rather than a
  reading exercise.

Events are append-only and never mutated once written.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class EventType(str, Enum):
    SESSION_META = "session_meta"
    PLAYER_INPUT = "player_input"
    RULES_RESOLUTION = "rules_resolution"
    GM_ADJUDICATION = "gm_adjudication"
    GM_NARRATION = "gm_narration"
    NPC_TURN = "npc_turn"
    CANON_WRITE = "canon_write"
    INVENTORY_CHANGE = "inventory_change"
    CHRONICLE_WRITE = "chronicle_write"
    COMBAT_START = "combat_start"
    COMBAT_TURN = "combat_turn"
    HIT_POINT_CHANGE = "hit_point_change"
    COMBAT_END = "combat_end"
    ESCALATION = "escalation"
    COST = "cost"


class CallStatus(str, Enum):
    """D-008's pending-state discipline: log intent *before* an external call.

    A crash between `PENDING` and its resolution is then reconstructable — the mystery's
    lesson, and the reason a model call is two writes rather than one.
    """

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _Event(BaseModel):
    """Common envelope. `seq` is assigned by the emitter, not the caller."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    seq: int = Field(ge=0)
    ts: datetime = Field(default_factory=utcnow)
    session_id: str = Field(min_length=1)


# --- session_meta ----------------------------------------------------------


class SeatInfo(BaseModel):
    """The resolved model seat, so a log says what actually ran (never a hardcoded id)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str
    model: str
    endpoint: str | None = None


class SessionMeta(_Event):
    type: Literal[EventType.SESSION_META] = EventType.SESSION_META
    schema_version: int = SCHEMA_VERSION
    dndc_version: str
    #: Commit the engine ran at — the mystery's lesson, stamped every session.
    commit_sha: str | None = None
    #: True when the working tree had uncommitted changes: the SHA alone then does not
    #: describe the code that ran, which matters for replay claims.
    dirty_worktree: bool = False
    billing: str
    campaign: str | None = None
    seats: dict[str, SeatInfo] = Field(default_factory=dict)
    gameplay: dict[str, str] = Field(default_factory=dict)
    srd_pin: str | None = None
    #: Master seed. Recorded so the whole session's randomness is reconstructable.
    seed: int | None = None
    note: str | None = None


# --- play ------------------------------------------------------------------


class PlayerInput(_Event):
    type: Literal[EventType.PLAYER_INPUT] = EventType.PLAYER_INPUT
    player: str
    character: str | None = None
    text: str


class DiceRoll(BaseModel):
    """One rolled expression, faces and all — enough to verify the total by hand."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expression: str
    rolls: tuple[int, ...] = ()
    kept: tuple[int, ...] = ()
    modifier: int = 0
    total: int


class RulesResolution(_Event):
    """A deterministic outcome from the rules core. Never produced by a model (D-001)."""

    type: Literal[EventType.RULES_RESOLUTION] = EventType.RULES_RESOLUTION
    #: check | save | attack | damage | initiative | roll
    kind: str
    actor: str | None = None
    target: str | None = None
    ability: str | None = None
    skill: str | None = None
    dc: int | None = None
    advantage: str | None = None
    roll: DiceRoll
    success: bool | None = None
    critical: bool | None = None
    #: Seed this roll came from, so the resolution replays exactly.
    seed: int | None = None
    detail: dict[str, object] = Field(default_factory=dict)


class GMAdjudication(_Event):
    """A GM ruling — the DC it set, and why. Phase 7 reads these for fairness."""

    type: Literal[EventType.GM_ADJUDICATION] = EventType.GM_ADJUDICATION
    situation: str
    ruling: str
    dc: int | None = None
    ability: str | None = None
    #: `seq` of the rules_resolution this ruling governed, so the pair is auditable.
    resolution_seq: int | None = None
    rationale: str | None = None


class GMNarration(_Event):
    type: Literal[EventType.GM_NARRATION] = EventType.GM_NARRATION
    text: str
    scene: str | None = None
    model: str | None = None
    status: CallStatus = CallStatus.COMPLETE
    #: Shared by the pending and terminal writes of one model call (OD-9). Adjacency
    #: pairing survives Phase 1 but breaks under Phase 4's interleaved NPC calls.
    call_id: str | None = None
    scaffolding: str | None = None


class NPCTurn(_Event):
    """An NPC utterance and the gatekeeper's verdict on it (D-003)."""

    type: Literal[EventType.NPC_TURN] = EventType.NPC_TURN
    npc: str
    text: str
    model: str | None = None
    status: CallStatus = CallStatus.COMPLETE
    #: Shared by the pending and terminal writes of one model call (OD-9).
    call_id: str | None = None
    #: pass | blocked | revised — a blocked draft is still logged; leaks are the study.
    gatekeeper_verdict: str | None = None
    gatekeeper_reason: str | None = None
    knowledge_scope: str | None = None


class CanonOperation(str, Enum):
    """What a `canon_write` did to the ledger (D-008, amended 2026-08-09)."""

    CREATE = "create"
    #: Replaces an earlier entry, which is named in `supersedes`.
    SUPERSEDE = "supersede"
    #: New narration contradicted an existing entry and **the entry was kept**. The
    #: ledger never quietly updates itself to match drift — measuring drift is the point,
    #: and a ledger that follows the model has nothing left to measure against.
    CONFLICT = "conflict"


class CanonSource(str, Enum):
    """Which mechanism wrote a `canon_write` (D-008, amended 2026-08-12).

    The ledger has more than one writer and they are not equally trustworthy: `gm_tag` is
    the GM seat declaring a fact as it narrates, `sweep` is a local 8B inferring after the
    fact what the GM established and forgot to declare. Phase 7 cannot weigh a ledger
    whose rows do not say which of those wrote them.
    """

    #: The GM's inline `[[CANON: ...]]`, written as it narrated (P2.2).
    GM_TAG = "gm_tag"
    #: The end-of-session utility-tier backstop (P2.3). Table-confirmed before it lands.
    SWEEP = "sweep"
    #: Backstory facts from guided character creation (D-005, P1.4).
    CO_CREATION = "co_creation"
    #: Hand-written into `canon.yaml` by a human. No model involved.
    AUTHORED = "authored"


class CanonWrite(_Event):
    """A canon-ledger mutation with provenance (D-002). Feeds canon-drift metrics."""

    type: Literal[EventType.CANON_WRITE] = EventType.CANON_WRITE
    entry_id: str
    #: A `CanonScope` value: world | player_known | gm_only | npc_belief | character.
    scope: str
    operation: CanonOperation = CanonOperation.CREATE
    statement: str
    established_by: str | None = None
    supersedes: str | None = None
    source: CanonSource = CanonSource.GM_TAG
    #: False for a proposal the table declined — which is logged, and does **not** enter
    #: the ledger. Same field and same argument as `inventory_change.confirmed`: what a
    #: model proposed and the humans rejected measures the proposer, and only exists as a
    #: measurement if the rejection is written down.
    confirmed: bool = True


class InventoryDirection(str, Enum):
    GAIN = "gain"
    LOSE = "lose"


class InventoryChange(_Event):
    """An item entering or leaving a sheet (D-008, amended 2026-08-09).

    Items are state, so the GM may propose a change but never perform one — same split as
    `[[CHECK]]`. A proposal the table declined is logged too, with `confirmed: false`:
    what the GM thought had happened and the players did not is exactly the divergence
    Phase 7 is built to see.
    """

    type: Literal[EventType.INVENTORY_CHANGE] = EventType.INVENTORY_CHANGE
    character: str
    item: str
    quantity: int = Field(default=1, ge=1)
    direction: InventoryDirection
    established_by: str | None = None
    confirmed: bool = True
    #: Whether the sheet changed *as proposed* (D-008, amended 2026-08-13). `confirmed`
    #: is the humans agreeing; this is the engine managing it. They come apart when the
    #: GM narrates losing something the sheet never held — the fiction/state divergence
    #: the whole task exists to measure, which no join over these rows could recover.
    applied: bool = True
    turn_seq: int | None = None


class ChronicleWrite(_Event):
    """One compression pass over past sessions — D-002's third memory layer.

    Deliberately not a `canon_write`: a chronicle entry is lossy prose about many turns,
    a canon entry is a discrete fact with provenance. Conflating them would let a
    compression artifact enter the ledger as an established fact.
    """

    type: Literal[EventType.CHRONICLE_WRITE] = EventType.CHRONICLE_WRITE
    covers_sessions: tuple[str, ...] = ()
    summary: str
    model: str | None = None
    token_estimate: int | None = Field(default=None, ge=0)


class CombatSide(str, Enum):
    """Mirrors `rules.combat.Side`. Spelled again here because the log is a wire format
    with its own compatibility promises, and a schema that imports its vocabulary from
    the engine changes shape whenever the engine is refactored."""

    PARTY = "party"
    FOES = "foes"


class CombatOutcome(str, Enum):
    PARTY = "party"
    FOES = "foes"
    #: Everyone down. Rare, and it happens.
    DRAW = "draw"


class DamageEffect(str, Enum):
    """How the target's body answered the damage type (D-008, amended 2026-08-15)."""

    NORMAL = "normal"
    RESISTANT = "resistant"
    VULNERABLE = "vulnerable"
    IMMUNE = "immune"


class CombatantRecord(BaseModel):
    """A combatant as the fight received them — hit points included.

    The reason `combat_start` exists. Monster hit points may be rolled (P3.2), so without
    this every later row in the fight refers to a creature of unknown durability and the
    fight cannot be replayed or read.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    side: CombatSide
    max_hp: int = Field(ge=0)
    current_hp: int = Field(ge=0)
    armor_class: int = Field(ge=0)
    is_player: bool = False


class CombatStart(_Event):
    """A fight begins: who is in it, in what order, from what seed."""

    type: Literal[EventType.COMBAT_START] = EventType.COMBAT_START
    encounter_id: str
    combatants: tuple[CombatantRecord, ...] = ()
    #: Combatant ids, first to last in the initiative order.
    order: tuple[str, ...] = ()
    seed: int | None = None
    round: int = Field(default=1, ge=1)


class TargetSource(str, Enum):
    """Who picked what this combatant attacked (D-008, amended 2026-08-15 for P3.7).

    The fallback is always recorded *as* a fallback: a fight must never stall on a missing
    tag, and Phase 7 must never have to guess whether a choice was made or defaulted.
    """

    #: The GM declared it with `[[TARGET: ...]]` and the engine honoured it.
    DECLARED = "declared"
    #: Nothing was declared, so the deterministic policy chose.
    POLICY = "policy"
    #: A declaration named someone already down or not in the fight. Declarations are
    #: written a turn ahead, so events can overtake them — and "the GM chose badly" and
    #: "the GM's choice expired" are different findings.
    STALE = "stale"


class CombatTurn(_Event):
    """Whose turn it is, in which round, and who they went for.

    Derivable in principle from the order and the rows between; derivable-in-principle is
    where analysis goes wrong, and one row per turn makes "which round was this narration
    in" a lookup rather than a simulation.
    """

    type: Literal[EventType.COMBAT_TURN] = EventType.COMBAT_TURN
    encounter_id: str
    round: int = Field(ge=1)
    combatant: str
    #: Who this combatant attacked, and who decided. `None` for a turn that attacked
    #: nobody — a death save, or a monster with nothing left standing to hit.
    target: str | None = None
    target_source: TargetSource | None = None


class HitPointChange(_Event):
    """The state change, as distinct from the roll that caused it.

    The `inventory_change` argument exactly: the engine performs a change to a sheet the
    GM must never invent, so it is its own row. The two genuinely come apart — a fall
    damages with no attack roll, and resistance changes what a roll means without
    changing the roll.
    """

    type: Literal[EventType.HIT_POINT_CHANGE] = EventType.HIT_POINT_CHANGE
    encounter_id: str | None = None
    combatant: str
    before: int = Field(ge=0)
    after: int = Field(ge=0)
    #: Positive for damage, negative for healing. What actually came off hit points,
    #: after resistance and temporary hit points.
    amount: int
    damage_type: str | None = None
    effect: DamageEffect = DamageEffect.NORMAL
    #: Soaked by temporary hit points before real ones were touched.
    temporary_absorbed: int = Field(default=0, ge=0)
    dropped: bool = False
    killed: bool = False
    #: `seq` of the `rules_resolution` that rolled this, when a roll caused it — the same
    #: link `gm_adjudication` uses.
    resolution_seq: int | None = None


class CombatEnd(_Event):
    """A fight's outcome, length and survivors — what makes lethality measurable."""

    type: Literal[EventType.COMBAT_END] = EventType.COMBAT_END
    encounter_id: str
    outcome: CombatOutcome
    rounds: int = Field(default=0, ge=0)
    survivors: tuple[str, ...] = ()


class Escalation(_Event):
    """A threshold-moment escalation to the Opus seat (D-004 / OD-3)."""

    type: Literal[EventType.ESCALATION] = EventType.ESCALATION
    trigger: str
    from_model: str
    to_model: str
    reason: str | None = None


class Cost(_Event):
    """Per-call telemetry.

    In subscription mode `usd` is what the call *would* have cost at API rates, flagged
    by `would_have_cost` — that is what makes the D-004 billing toggle measurable
    instead of a matter of opinion.
    """

    type: Literal[EventType.COST] = EventType.COST
    seat: str
    model: str
    billing: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    usd: float | None = None
    would_have_cost: bool = False
    #: `seq` of the event this call produced.
    for_seq: int | None = None
    #: The model call this cost belongs to (OD-9) — same id as its gm_narration /
    #: npc_turn pair, so cost attribution survives interleaved calls.
    call_id: str | None = None


Event = Annotated[
    SessionMeta
    | PlayerInput
    | RulesResolution
    | GMAdjudication
    | GMNarration
    | NPCTurn
    | CanonWrite
    | InventoryChange
    | ChronicleWrite
    | CombatStart
    | CombatTurn
    | HitPointChange
    | CombatEnd
    | Escalation
    | Cost,
    Field(discriminator="type"),
]

EVENT_MODELS: dict[EventType, type[_Event]] = {
    EventType.SESSION_META: SessionMeta,
    EventType.PLAYER_INPUT: PlayerInput,
    EventType.RULES_RESOLUTION: RulesResolution,
    EventType.GM_ADJUDICATION: GMAdjudication,
    EventType.GM_NARRATION: GMNarration,
    EventType.NPC_TURN: NPCTurn,
    EventType.CANON_WRITE: CanonWrite,
    EventType.INVENTORY_CHANGE: InventoryChange,
    EventType.CHRONICLE_WRITE: ChronicleWrite,
    EventType.COMBAT_START: CombatStart,
    EventType.COMBAT_TURN: CombatTurn,
    EventType.HIT_POINT_CHANGE: HitPointChange,
    EventType.COMBAT_END: CombatEnd,
    EventType.ESCALATION: Escalation,
    EventType.COST: Cost,
}
