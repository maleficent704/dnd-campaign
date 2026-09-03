"""The D-008 event vocabulary, typed.

Every event the engine emits is one of these families. The vocabulary is
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
    BELIEF_CHANGE = "belief_change"
    INVENTORY_CHANGE = "inventory_change"
    CHRONICLE_WRITE = "chronicle_write"
    RECAP = "recap"
    BACKGROUND_WRITE = "background_write"
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
    #: The session a save point was picked up from (P5.1). When a session is resumed into
    #: its own log this names that same session, and the second row is what says the
    #: process restarted — possibly onto a different commit, seat or seed.
    resumed_from: str | None = None
    #: Turns already behind the resume. Without it a log that opens at turn fifteen reads
    #: like a log with fourteen turns missing.
    resumed_turns: int = 0
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
    #: `pass` | `revised` | `blocked` | `unchecked` (D-008 item 19). `None` means no gate
    #: was configured at all — kept distinct from `unchecked`, which is a gate that was
    #: asked and could not answer: one is configuration, the other is an incident. Neither
    #: is ever recorded as `pass`, because a row claiming a check succeeded when none ran
    #: is worse than a silent one — it gets believed.
    gatekeeper_verdict: str | None = None
    gatekeeper_reason: str | None = None
    #: The pre-gate text, set **only when the gate changed it** (D-008 item 20). Every leak
    #: rate has pre-censor drafts as its denominator, and a gate that quietly improved the
    #: record of its own performance would be an instrument measuring itself.
    draft: str | None = None
    #: The canon entry ids this NPC was permitted, comma-joined, as of this call (D-008
    #: item 17). Ids and not a count: a leak is only measurable against what was in scope
    #: at the time, and the scope moves as canon is written during a session.
    knowledge_scope: str | None = None
    #: Which Ollama host served the call (D-008 item 18) — the routing layer's only
    #: observable, and the difference between "the 70B answered" and "the 70B on the box
    #: we expected answered".
    endpoint: str | None = None
    #: What the GM asked this character to address, verbatim from the `[[SPEAK:]]` tag
    #: (D-008 item 22). The stimulus beside the response: an NPC that names the tunnel
    #: unprompted and one that was *told to talk about the tunnel* by a GM holding
    #: `gm_only` canon are different failures, and `text` alone cannot tell them apart.
    direction: str | None = None


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
    #: The supersession pass (P4.6, D-008 item 25). Only ever on a `supersede` row: a
    #: second call judged that a character's new belief replaced an older one. Never
    #: writes a fact, only retires one — which is why it is worth telling apart from
    #: `gm_tag`, the seat that authored the change it is acting on.
    STANCE = "stance"


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


class StanceStatus(str, Enum):
    """Whether the supersession pass reached a verdict (D-008 item 26)."""

    #: A judge was asked and answered. `retired` is its decision, empty or not.
    JUDGED = "judged"
    #: No judge was configured, or it could not answer. Nothing was retired, which is
    #: exactly what happened before P4.6 existed — the fail-open direction.
    UNJUDGED = "unjudged"


class BeliefChange(_Event):
    """A character changed their mind, and what that retired (P4.6, D-003's OD-13 port).

    Separate from the `canon_write` rows it produces, for the same reason `unchecked`
    exists on the gate: **a pass that ran and retired nothing must not look like a pass
    that never ran.** `considered` minus `retired` is what the judge saw and left standing,
    which is the only way to tell a conservative judge from an absent one.
    """

    type: Literal[EventType.BELIEF_CHANGE] = EventType.BELIEF_CHANGE
    npc: str
    #: What they now believe, verbatim from the tag.
    belief: str
    #: The new canon entry. `None` when the ledger already held this belief word for word,
    #: which establishes nothing and is not an error — the pass still runs, because a
    #: restated belief can still retire an older one.
    entry_id: str | None = None
    #: The belief ids in force when the pass ran, comma-joined. Ids and not a count, for
    #: the same reason as `npc_turn.knowledge_scope`: what was standing at the time is
    #: what the decision was made against, and it moves during a session.
    considered: str | None = None
    #: The ids this change superseded, comma-joined. Empty means nothing was retired.
    retired: str | None = None
    status: StanceStatus = StanceStatus.JUDGED
    #: Why, when `unjudged` — an unreachable host, an unparseable verdict, no judge.
    reason: str | None = None
    model: str | None = None
    call_id: str | None = None
    #: The raw `[[BELIEF: ...]]` tag that declared it.
    established_by: str | None = None
    turn_seq: int | None = Field(default=None, ge=0)


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


class RecapStatus(str, Enum):
    """How a "previously on..." pass ended (D-008 item 28)."""

    #: Written and shown to the table.
    WRITTEN = "written"
    #: Rejected by the grounding check after a retry — it named people the record did
    #: not. Nothing was shown; the same posture the chronicle takes, and for the same
    #: reason: no recap is better than a confident wrong one.
    UNGROUNDED = "ungrounded"
    #: No call was made or none came back — no chronicle to read, the box asleep, the
    #: table having passed --no-recap. The session plays on regardless.
    SKIPPED = "skipped"


class Recap(_Event):
    """The "previously on..." the players were shown at pickup (D-008 item 28).

    Deliberately not a `chronicle_write`: that is a stored layer of the campaign's
    memory and this is a fresh read of it, shown to humans and kept nowhere. It writes
    no canon — the recapper is handed no store and has nothing to write with.
    """

    type: Literal[EventType.RECAP] = EventType.RECAP
    #: What the table was actually shown. The only generated text in the system that
    #: reaches the players without passing through a prompt, so the log is the only
    #: record of it.
    text: str = ""
    #: Where the recap thinks the party is standing. A proposal, never applied unheard.
    scene: str | None = None
    scene_accepted: bool = False
    #: Chronicle entries read, by session id.
    covers: tuple[str, ...] = ()
    status: RecapStatus = RecapStatus.WRITTEN
    #: Names the grounding check refused, when it refused.
    invented: tuple[str, ...] = ()
    model: str | None = None
    call_id: str | None = None


class BackgroundWrite(_Event):
    """An original background the GM proposed during co-creation (D-008, item 16).

    The first campaign content the GM writes that is *mechanical* — canon is fiction and
    an inventory change moves something the ruleset already defines, but a background
    grants proficiencies. So the row carries the whole shape, not a reference: a log
    should say what a character was granted without needing the campaign file that
    version of it was written into.

    `confirmed` is the table agreeing; `applied` is the campaign file changing. They come
    apart when the background already exists identically — accepted, nothing written. A
    refused proposal is logged with `confirmed: false` and never persisted.
    """

    type: Literal[EventType.BACKGROUND_WRITE] = EventType.BACKGROUND_WRITE
    name: str
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    #: Languages the background teaches, named — at most one, per the ruling's "small
    #: extra". Named rather than "one of your choice" because a grant with a decision left
    #: in it is a grant that gets left half-spent.
    languages: tuple[str, ...] = ()
    feature: str = ""
    #: The character it was proposed for. A background outlives them and is reusable, but
    #: whose interview produced it is the provenance that matters.
    character: str | None = None
    established_by: str | None = None
    confirmed: bool = True
    applied: bool = True


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
    #: Wall-clock milliseconds (D-008 item 23). Every backend has measured this since
    #: Phase 1 and nothing wrote it down — it went to a console and was thrown away, which
    #: is how a timing question came to be answered from memory, wrongly (2026-09-02 (e)).
    #: On a local seat the latency *is* a finding: model eviction, a fallback to a second
    #: endpoint and a cold load all announce themselves here and nowhere in a token count.
    latency_ms: int | None = None


Event = Annotated[
    SessionMeta
    | PlayerInput
    | RulesResolution
    | GMAdjudication
    | GMNarration
    | NPCTurn
    | CanonWrite
    | BeliefChange
    | InventoryChange
    | ChronicleWrite
    | Recap
    | BackgroundWrite
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
    EventType.BELIEF_CHANGE: BeliefChange,
    EventType.INVENTORY_CHANGE: InventoryChange,
    EventType.CHRONICLE_WRITE: ChronicleWrite,
    EventType.RECAP: Recap,
    EventType.BACKGROUND_WRITE: BackgroundWrite,
    EventType.COMBAT_START: CombatStart,
    EventType.COMBAT_TURN: CombatTurn,
    EventType.HIT_POINT_CHANGE: HitPointChange,
    EventType.COMBAT_END: CombatEnd,
    EventType.ESCALATION: Escalation,
    EventType.COST: Cost,
}
