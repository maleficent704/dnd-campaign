"""The end-of-session canon sweep (P2.3) — the backstop for inline extraction.

P2.2 has the GM declare facts inline as it narrates. The first live run showed exactly
the failure mode that design has: the opening scene tagged nothing at all, and a turn
that established four concrete things about the road tagged none of them. Inline
extraction gets what the GM remembers to declare, which is not everything it establishes.

So a second pass reads the session back afterwards and proposes what was missed. It runs
on the utility seat — a local 8B on toto-llm — which makes it free, which is why it can
be thorough rather than selective. Three things keep a small model from quietly corrupting
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

**Every proposal is checked against the transcript** (`_grounded`). The first live run
produced a fact about a person who does not exist in the session it was reading — the
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

import re
import time
from dataclasses import dataclass, field
from typing import Sequence

from dndc.gm.canon import CanonEntry, CanonScope, render_entries
from dndc.gm.canontag import find_canon_tags
from dndc.gm.context import Turn
from dndc.gm.templates import render_template
from dndc.logging import SessionLog
from dndc.memory.canon_store import CanonStore, normalise
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

#: Neither `api` nor `subscription`: this call ran on hardware in the house and cost
#: nothing either way. Recorded as its own value so campaign cost analysis (OD-16) can
#: exclude it by seat *and* by billing rather than by assuming zero.
LOCAL_BILLING = "local"

_NO_CANON = "(nothing recorded yet)"
_NO_PARTY = "(none named — treat any recurring first-person actor as a player)"

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

#: Words this short carry no evidence either way; requiring them to match would reject
#: honest paraphrase over "the" and "was".
_MIN_CONTENT_LEN = 4

#: How much of a proposal's substance has to appear in the text it was drawn from. Set by
#: what the first live run needed: a fact the model copied out of the prompt's own worked
#: examples scored near zero, and every genuine extraction scored well above this.
_MIN_OVERLAP = 0.5


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
            transcript = _transcript(chunk)
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
        drawn from — see `_grounded`. Returns the survivors and how many were thrown out
        as ungrounded, because that count is the honest measure of the seat's model.
        """
        proposals = []
        ungrounded = 0
        vocabulary = _vocabulary(transcript)
        for tag in find_canon_tags(text):
            statement = " ".join(tag.text.split())
            if not statement or len(statement) > MAX_FACT_CHARS:
                continue
            if not _grounded(statement, vocabulary):
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
            seat="utility",
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd,
            call_id=response.call_id,
        )


def _stem(word: str) -> str:
    """A word as the grounding check compares it.

    Only the possessive is stripped, and only because "Ashmill's waystation" is what a
    paraphrase of "the waystation at Ashmill" actually looks like — the check rejected
    exactly that until this existed. Nothing further is stemmed: the point is to compare
    words, and a matcher clever enough to equate "burned" with "burning" is also clever
    enough to accept an invention.
    """
    folded = word.casefold().strip("-'’")
    for suffix in ("'s", "’s"):
        if folded.endswith(suffix):
            return folded[: -len(suffix)]
    return folded


def _vocabulary(text: str) -> set[str]:
    return {_stem(word) for word in _WORD.findall(text)}


def _grounded(statement: str, vocabulary: set[str]) -> bool:
    """Does this fact actually come from the text it claims to?

    The second live run needed this. Given a tightly-worded prompt with three worked
    examples, `llama3.1:8b` answered with the three worked examples — including a person
    and a place that appear nowhere in the transcript it was reading. Prose cannot stop
    that; it *was* prose that caused it. So the claim is checked against its source, in
    code, and the check holds whatever model ends up in the utility seat.

    Two tests, and a proposal must pass both:

    * **Every name it uses must appear in the transcript.** A capitalised word that is not
      sentence-initial is a name, and a name the session never mentioned is the signature
      of a model reciting rather than reading — the exact failure that was observed.
    * **Half its substance must appear too.** Loose enough for honest paraphrase, which is
      what a good extraction is, and tight enough to catch a plausible invention.
    """
    words = _WORD.findall(statement)
    if not words:
        return False

    for word in words[1:]:
        if word[0].isupper() and _stem(word) not in vocabulary:
            return False

    content = [_stem(word) for word in words if len(_stem(word)) >= _MIN_CONTENT_LEN]
    if not content:
        # Nothing long enough to check. The names passed, so let the table judge it.
        return True
    matched = sum(1 for word in content if word in vocabulary)
    return matched / len(content) >= _MIN_OVERLAP


def _chunks(turns: Sequence[Turn], size: int) -> list[Sequence[Turn]]:
    return [turns[start:start + size] for start in range(0, len(turns), size)]


def _transcript(turns: Sequence[Turn]) -> str:
    """The session as the clerk reads it.

    Player input is included even though the sweep must not record it. Half the narration
    in a session is a reply — "you push it open, and the hinges give" means nothing
    without the line that prompted it — and a clerk given only the answers writes down
    facts that are missing their subject.
    """
    blocks = []
    for index, turn in enumerate(turns, start=1):
        lines = [f"--- exchange {index} ---"]
        if turn.opening:
            lines.append("(the session opens)")
        elif turn.player_input.strip():
            lines.append(f"{turn.speaker or 'A player'}: {turn.player_input.strip()}")
        lines.append(f"GM: {turn.narration.strip()}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
