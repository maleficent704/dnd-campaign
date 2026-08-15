"""The end-of-session canon sweep (P2.3) — the backstop for inline extraction.

P2.2 has the GM declare facts inline as it narrates. The first live run showed exactly
the failure mode that design has: the opening scene tagged nothing at all, and a turn
that established four concrete things about the road tagged none of them. Inline
extraction gets what the GM remembers to declare, which is not everything it establishes.

So a second pass reads the session back afterwards and proposes what was missed. It runs
on the interactive utility seat — a local 8B on toto-llm — which makes it free, which is
why it can be thorough rather than selective. It is the seat the table waits on: the
proposals are read out at the end of the evening, so seconds matter and over-proposing
does not (Fable, 2026-08-14). Three things keep a small model from quietly corrupting
the thing the whole project exists to measure:

**It can only ever write `player_known`.** Not a rule in the prompt — a constant in the
code. The sweep reads narration, and narration is by definition what the table was told,
so `player_known` is the only scope its evidence supports. It therefore cannot mint a
secret, cannot put words in an NPC's mouth, and cannot declare world truth that nobody at
the table has seen. Same posture as OD-11 and OD-12: protection by construction, not by
instruction, because an instruction a model follows on turn 3 is one it drops on turn 90.

**It never sees `gm_only` canon.** Its proposals are printed to the table for
confirmation, so anything it reads is one echo away from the players' screen. A model
that was never given the secret cannot leak it.

**Every proposal is checked against the transcript** (`memory/grounding.py`). The first
live run produced a fact about a person who does not exist in the session it read — the
model had recited the prompt's own worked examples back. A claim that cannot be found in
its source is dropped before anyone sees it.

**It proposes; the table decides.** The GM seat's own tags file automatically — that is a
Sonnet-class model declaring an intent. This is an 8B inferring one, and its output is
checked before it becomes ground truth. A declined proposal is still logged
(`confirmed: false`), because the sweep's precision is a number Phase 7 should be able to
compute rather than guess at.

The sweep never raises. A session ending in a traceback because the GPU box was asleep
would be a worse bug than the one this fixes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from dndc.gm.canon import CanonEntry, CanonScope, render_entries
from dndc.gm.canontag import find_canon_tags
from dndc.gm.context import Turn, render_transcript
from dndc.gm.templates import render_template
from dndc.logging import SessionLog
from dndc.memory.canon_store import CanonStore, normalise
from dndc.memory.grounding import MIN_CONTENT_LEN, WORD, grounded, stem, vocabulary
from dndc.models import INTERACTIVE_SEAT
from dndc.models.base import GMBackend, GMBackendError, GMRequest, Message, Role
from dndc.schema.events import CanonSource, Cost

#: The only scope a sweep may write. See the module docstring — this being a constant
#: rather than a prompt instruction is the point.
SWEEP_SCOPE = CanonScope.PLAYER_KNOWN

#: Turns per call. A small model reading eight turns finds more than the same model
#: reading forty, and local inference is free, so the pass is chunked rather than
#: one-shot. Chunks are sequential so each one can be told what the earlier ones found.
DEFAULT_CHUNK_TURNS = 8

#: Ceilings on what one sweep may propose. A local model that loses the plot can emit a
#: hundred lines of restated atmosphere, and the confirmation prompt has to stay readable.
#: Whatever is dropped is counted and reported — a silent cap reads as "found everything".
MAX_PROPOSALS = 40
MAX_FACT_CHARS = 300

#: Low, not zero. This is extraction, not narration — the same session read twice should
#: produce the same facts, and at the seat's default the first live run answered "23
#: facts" one time and "none" the next. Not zero because a fact can be phrased several
#: ways and greedy decoding on a small model tends to lock onto whatever it said first.
SWEEP_TEMPERATURE = 0.1

#: How much two proposals must overlap before the confirmation prompt treats them as one
#: fact phrased twice. High on purpose — see `cluster`. Measured against the 08-13 live
#: run: the four barking-dog restatements group, and facts that merely share a subject do
#: not.
SIMILAR_ENOUGH = 0.6

#: Below this many content words, a statement is never clustered — see `cluster`.
MIN_CLUSTER_WORDS = 3

#: Neither `api` nor `subscription`: this call ran on hardware in the house and cost
#: nothing either way. Recorded as its own value so campaign cost analysis (OD-16) can
#: exclude it by seat *and* by billing rather than by assuming zero.
LOCAL_BILLING = "local"

_NO_CANON = "(nothing recorded yet)"
_NO_PARTY = "(none named — treat any recurring first-person actor as a player)"


@dataclass(frozen=True)
class SweepProposal:
    """One fact the sweep thinks the session established and nobody wrote down."""

    text: str
    #: Always `SWEEP_SCOPE`. Present so a proposal reads like the thing it becomes.
    scope: CanonScope = SWEEP_SCOPE
    raw: str = ""


@dataclass
class SweepReport:
    """What one sweep did, including having failed."""

    proposals: list[SweepProposal] = field(default_factory=list)
    turns_read: int = 0
    calls: int = 0
    model: str | None = None
    #: Proposals discarded by `MAX_PROPOSALS` / `MAX_FACT_CHARS`, so the CLI can say so.
    dropped: int = 0
    #: Proposals thrown out because they were not in the transcript they claimed to come
    #: from. A number worth watching: it is a direct measurement of the utility seat.
    ungrounded: int = 0
    duration_ms: int = 0
    #: Set when the seat could not be reached. `proposals` is then empty and nothing was
    #: written; the session ends normally.
    error: str | None = None

    @property
    def ran(self) -> bool:
        return self.error is None


class CanonSweep:
    """Reads a session back and proposes the canon the GM did not declare."""

    def __init__(
        self,
        backend: GMBackend,
        store: CanonStore,
        log: SessionLog | None = None,
        max_tokens: int = 2048,
        chunk_turns: int = DEFAULT_CHUNK_TURNS,
        billing: str = LOCAL_BILLING,
        party: Sequence[str] = (),
    ) -> None:
        self.backend = backend
        self.store = store
        self.log = log
        self.max_tokens = max_tokens
        self.chunk_turns = max(1, chunk_turns)
        self.billing = billing
        #: Who the player characters are. Named in the prompt because the first live run
        #: filled a third of its proposals with what the party did — "Corin checks the
        #: wagons" is the session, not the world, and a small model cannot tell the
        #: difference unless it is told which names belong to players.
        self.party = tuple(party)

    # --- proposing ---------------------------------------------------------

    def propose(self, turns: Sequence[Turn]) -> SweepReport:
        """Read the session and return what it thinks was established, unfiled.

        Nothing here touches the ledger. A crash between proposing and filing loses only
        proposals, which is why this call is not wrapped in the pending/terminal logging
        discipline a narration call gets — there is no half-written state to reconstruct.
        """
        report = SweepReport(turns_read=len(turns))
        playable = [turn for turn in turns if turn.narration.strip()]
        if not playable:
            return report

        started = time.monotonic()
        seen: set[str] = set()
        found: list[SweepProposal] = []

        for chunk in _chunks(playable, self.chunk_turns):
            transcript = render_transcript(chunk)
            try:
                response = self.backend.generate(
                    self._request(transcript, extra_known=[p.text for p in found])
                )
            except GMBackendError as exc:
                report.error = str(exc)
                break
            except Exception as exc:  # a local box that went away mid-sweep
                report.error = f"{type(exc).__name__}: {exc}"
                break

            report.calls += 1
            report.model = response.model
            self._emit_cost(response)
            if response.refused:
                continue

            candidates, ungrounded = self._parse(response.text, transcript)
            report.ungrounded += ungrounded
            for candidate in candidates:
                key = normalise(candidate.text)
                if key in seen:
                    continue
                seen.add(key)
                found.append(candidate)

        report.duration_ms = int((time.monotonic() - started) * 1000)
        if len(found) > MAX_PROPOSALS:
            report.dropped = len(found) - MAX_PROPOSALS
            found = found[:MAX_PROPOSALS]
        report.proposals = found
        return report

    def _parse(self, text: str, transcript: str) -> tuple[list[SweepProposal], int]:
        """The sweep answers in the GM's own `[[CANON: ...]]` form, so one parser serves.

        That is not decoration. A shared format means the preamble a small model cannot
        help writing ("Here are the facts I found:") is ignored structurally rather than
        by a heuristic, and it means there is one place to fix a parsing bug instead of
        two that drift apart. Whatever scope the model claims is discarded: see
        `SWEEP_SCOPE`.

        Everything that survives is then checked against the transcript it was supposedly
        drawn from — see `memory/grounding.py`. Returns the survivors and how many were thrown out
        as ungrounded, because that count is the honest measure of the seat's model.
        """
        proposals = []
        ungrounded = 0
        known = vocabulary(transcript)
        for tag in find_canon_tags(text):
            statement = " ".join(tag.text.split())
            if not statement or len(statement) > MAX_FACT_CHARS:
                continue
            if not grounded(statement, known):
                ungrounded += 1
                continue
            if self.store.holds(statement, SWEEP_SCOPE):
                continue
            proposals.append(SweepProposal(text=statement, raw=tag.raw))
        return proposals, ungrounded

    def _request(self, transcript: str, extra_known: Sequence[str]) -> GMRequest:
        return GMRequest(
            system=render_template(
                "sweep",
                known_canon=self._known(extra_known),
                party=self._party(),
            ),
            messages=(Message(role=Role.USER, content=transcript),),
            max_tokens=self.max_tokens,
            # Nothing to cache: one call per session per chunk, and the prefix carries the
            # ledger, which has changed since the last time anyway.
            cache_system=False,
        )

    def _party(self) -> str:
        if not self.party:
            return _NO_PARTY
        return "\n".join(f"- {name}" for name in self.party)

    def _known(self, extra: Sequence[str]) -> str:
        """What the sweep is told is already on file — minus the secrets.

        `gm_only` entries are withheld even though including them would suppress a few
        duplicate proposals. The sweep's output is read aloud to the table; a secret it
        never received is a secret it cannot echo, and a handful of duplicates is a much
        cheaper problem than one leaked twist.
        """
        visible = [
            entry
            for entry in self.store.ledger.active()
            if entry.scope is not CanonScope.GM_ONLY
        ]
        lines = render_entries(visible) if visible else ""
        extra_lines = "\n".join(f"- {text}" for text in extra)
        body = "\n".join(part for part in (lines, extra_lines) if part.strip())
        return body or _NO_CANON

    # --- filing ------------------------------------------------------------

    def record(
        self,
        accepted: Sequence[SweepProposal],
        declined: Sequence[SweepProposal] = (),
        session: str | None = None,
    ) -> list[CanonEntry]:
        """File what the table kept; log what it threw away.

        No `turn` is recorded. A sweep fact was established somewhere across the session
        and the sweep does not know where — claiming a turn number would be inventing
        provenance, which is worse than having none.
        """
        written = []
        for proposal in accepted:
            entry = self.store.establish(
                proposal.text,
                scope=SWEEP_SCOPE,
                session=session,
                established_by=self._provenance(),
                source=CanonSource.SWEEP,
            )
            if entry is not None:
                written.append(entry)
        for proposal in declined:
            self.store.decline(
                proposal.text,
                scope=SWEEP_SCOPE,
                established_by=self._provenance(),
                source=CanonSource.SWEEP,
            )
        return written

    def _provenance(self) -> str:
        return f"end-of-session sweep ({getattr(self.backend, 'model', self.backend.name)})"

    # --- logging -----------------------------------------------------------

    def _emit_cost(self, response) -> None:
        if self.log is None:
            return
        usage = response.usage
        self.log.emit(
            Cost,
            seat=INTERACTIVE_SEAT,
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd,
            call_id=response.call_id,
        )


def _chunks(turns: Sequence[Turn], size: int) -> list[Sequence[Turn]]:
    return [turns[start:start + size] for start in range(0, len(turns), size)]


def cluster(
    proposals: Sequence[SweepProposal], threshold: float = SIMILAR_ENOUGH
) -> list[list[SweepProposal]]:
    """Group proposals that say the same thing in different words (Fable, 2026-08-14).

    A three-exchange live session produced twenty-two proposals containing the same
    barking dog four times, the same wobbling rail twice, and the same cold draught three
    times. All of them were real — grounding passed — and reading them was still work.

    **This is display, not truth.** Nothing is dropped and nothing is merged: every
    proposal is still shown, still offered, and still logged whichever way the table goes.
    The ruling was explicit that fuzzy matching must not silently suppress a fact (the
    npc-village lesson), so the clustering only decides what sits under what on screen.

    The threshold is deliberately high. Over-clustering costs the table a second glance at
    an indented line; under-clustering costs them nothing but a longer list. Given a
    choice between those two errors, take the longer list.
    """
    clusters: list[list[SweepProposal]] = []
    keys: list[set[str]] = []
    for proposal in proposals:
        words = _content_words(proposal.text)
        # A fact with almost no content words cannot be compared this way. "The bridge is
        # out" and "The bridge is fine" share their only long word and are opposites, so
        # a short statement always gets its own line.
        if len(words) >= MIN_CLUSTER_WORDS:
            for index, existing in enumerate(keys):
                if _similarity(words, existing) >= threshold:
                    clusters[index].append(proposal)
                    break
            else:
                clusters.append([proposal])
                keys.append(words)
            continue
        clusters.append([proposal])
        keys.append(set())
    return clusters


def similarity(left: str, right: str) -> float:
    """How much two statements say the same thing, 0..1.

    Public because two callers need one answer: the confirmation prompt groups by it
    (P2.3), and the drift baseline's recovery-stability diff decides by it whether a
    re-sweep found the same fact in different words (P2.6 / the 2026-08-15 ruling).
    """
    return _similarity(_content_words(left), _content_words(right))


def _content_words(text: str) -> set[str]:
    """The words a restatement would keep. Short words are noise for this purpose —
    "there is a" versus "the stair has" is phrasing, not content."""
    return {
        word
        for word in (stem(match) for match in WORD.findall(text))
        if len(word) >= MIN_CONTENT_LEN
    }


def _similarity(left: set[str], right: set[str]) -> float:
    """Jaccard. Two facts that share nine of ten content words are one fact twice."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
