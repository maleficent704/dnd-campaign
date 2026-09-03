"""Applying a change of mind (P4.6) — the tag, the judge, and the ledger writes.

Thin, like `npcturn.py`, and for the same reason: the decisions are elsewhere. What the
tag means is `gm/belieftag.py`, what a new belief retires is `gm/stance.py`, and what a
supersession does to the ledger is `memory/canon_store.py`. This calls them in order and
writes the rows.

The order is the part worth stating. The new belief is established **first**, on the GM's
own authority — it is a GM tag like `[[CANON]]`, and the judge has no say in whether the
character now thinks it. Only then is the standing set weighed, and the standing set is
read *before* the new entry lands so that a belief cannot be put up for retirement against
itself. What the judge decides is only ever what leaves the prompt.

A restated belief is not an error and not a no-op. `establish()` suppresses a fact the
ledger already holds word for word, so `entry` comes back `None` — but the pass still
runs, because a GM repeating a belief it already filed may well be doing so precisely to
retire an older one it forgot to retire the first time.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndc.gm.belieftag import BeliefTag
from dndc.gm.canon import CanonEntry, CanonScope
from dndc.gm.stance import StanceJudge, StanceJudgement
from dndc.logging import SessionLog
from dndc.memory.canon_store import CanonStore
from dndc.models import BATCH_SEAT, GMResponse
from dndc.memory.sweep import LOCAL_BILLING
from dndc.schema.events import BeliefChange, Cost, StanceStatus
from dndc.schema.npc import NPC


@dataclass(frozen=True)
class BeliefUpdate:
    """One applied change of mind, and what it cost the ledger."""

    npc: NPC
    #: What they now believe, verbatim from the tag.
    belief: str
    #: The new canon entry, or None when the ledger already held this belief.
    entry: CanonEntry | None
    judgement: StanceJudgement

    @property
    def retired(self) -> tuple[CanonEntry, ...]:
        return self.judgement.retired

    @property
    def judged(self) -> bool:
        return self.judgement.judged


@dataclass
class StanceKeeper:
    """Keeps one campaign's characters from holding two stories at once."""

    #: None means no judge is configured: beliefs are still filed, nothing is retired, and
    #: the row says `unjudged` rather than pretending a pass ran. Same discipline as the
    #: gate's `None`-vs-`unchecked` split — configuration and incident are different, and
    #: neither is ever recorded as a clean result.
    judge: StanceJudge | None = None
    log: SessionLog | None = None

    def apply(
        self,
        npc: NPC,
        tag: BeliefTag,
        store: CanonStore,
        session: str | None = None,
        turn: int | None = None,
    ) -> BeliefUpdate:
        """File the new belief, retire what it replaces, and log both."""
        standing = _standing(npc, store)
        entry = store.establish(
            tag.belief,
            scope=CanonScope.NPC_BELIEF,
            subject=npc.name,
            session=session,
            turn=turn,
            established_by=tag.raw or None,
        )

        if self.judge is None:
            judgement = StanceJudgement(
                considered=standing, judged=False, reason="no judge configured"
            )
        else:
            judgement = self.judge.judge(npc.name, tag.belief, standing)

        # A restated belief establishes no entry, so there is nothing for the old ones to
        # point at. Retiring them in favour of the entry already in the ledger would be
        # right but needs its id, which `establish` does not hand back on suppression;
        # rather than dig it out, the pass declines — a repeat is the rare case, and
        # silently retiring against an entry the caller never saw is worse than not.
        retired: list[CanonEntry] = []
        if entry is not None:
            for target in judgement.retired:
                store.retire(target.id, entry, established_by=tag.raw or None)
                retired.append(target)

        judgement = _with_retired(judgement, tuple(retired))
        self._emit(npc, tag, entry, judgement, turn)
        return BeliefUpdate(npc=npc, belief=tag.belief, entry=entry, judgement=judgement)

    def _emit_cost(self, response: GMResponse) -> None:
        """Bill a judge call to the seat that ran it.

        The gate does not do this and probably should; this pass does from the start,
        because it is the second thing on the critical path of a turn and (g) has already
        been caught quoting a latency from memory that the log could not confirm.
        """
        if self.log is None:
            return
        usage = response.usage
        self.log.emit(
            Cost,
            seat=BATCH_SEAT,
            model=response.model,
            billing=LOCAL_BILLING,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            usd=response.reported_usd,
            call_id=response.call_id,
            latency_ms=response.duration_ms,
        )

    def _emit(
        self,
        npc: NPC,
        tag: BeliefTag,
        entry: CanonEntry | None,
        judgement: StanceJudgement,
        turn: int | None,
    ) -> None:
        if self.log is None:
            return
        for response in judgement.responses:
            self._emit_cost(response)
        self.log.emit(
            BeliefChange,
            npc=npc.name,
            belief=tag.belief,
            entry_id=entry.id if entry is not None else None,
            # Ids and not counts, for the same reason as `npc_turn.knowledge_scope`: the
            # decision is only readable against what was standing when it was made.
            considered=",".join(item.id for item in judgement.considered) or None,
            retired=",".join(item.id for item in judgement.retired) or None,
            status=StanceStatus.JUDGED if judgement.judged else StanceStatus.UNJUDGED,
            reason=judgement.reason or None,
            model=judgement.model,
            call_id=judgement.call_id,
            established_by=tag.raw or None,
            turn_seq=turn,
        )


def _standing(npc: NPC, store: CanonStore) -> tuple[CanonEntry, ...]:
    """This character's own live beliefs, in ledger order.

    Their beliefs and nobody else's: `for_npc` already refuses to hand one character
    another's, and a change of mind must not reach across and retire a belief that is not
    this character's to abandon.
    """
    subject = npc.name.casefold()
    return tuple(
        entry
        for entry in store.ledger.for_npc(npc)
        if entry.scope is CanonScope.NPC_BELIEF
        and entry.subject
        and entry.subject.casefold() == subject
    )


def _with_retired(
    judgement: StanceJudgement, retired: tuple[CanonEntry, ...]
) -> StanceJudgement:
    """What was *actually* retired, which is not always what the judge chose — a restated
    belief mints no entry for the old ones to point at, and nothing moves."""
    if retired == judgement.retired:
        return judgement
    return StanceJudgement(
        retired=retired,
        considered=judgement.considered,
        judged=judgement.judged,
        reason=judgement.reason,
        responses=judgement.responses,
        model=judgement.model,
        call_id=judgement.call_id,
    )


__all__ = ["BeliefUpdate", "StanceKeeper"]
