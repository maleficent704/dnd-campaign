"""The drift test (P2.6) — does the established world survive, and does the GM keep it?

Phase 2 built the memory layers. This is the instrument that says whether they work, and
it is the thing the whole phase was for: D-002's rationale is that "without the ledger,
established facts mutate within one session", and that is a claim, not a measurement,
until something counts.

Two halves, deliberately different in kind.

**Survival — deterministic, no model.** Replay a session, recover what it established,
and assert every fact reaches the prompt a *second* session would send. This tests our
pipeline, not the GM's memory, so it must not depend on a model's mood: it either
survives or the pipeline has a hole.

**Contradiction — model-assisted, on the batch seat.** For each turn, does the narration
state something that cannot be true alongside a fact established earlier in the same
session? That is the number Fable asked P2.6 to produce before anyone chooses a
supersession fix (2026-08-14), and it cannot be computed deterministically: contradiction
is semantic.

The archived fixtures are the right baseline precisely because they predate P2.2 — they
carry no `[[CANON]]` tags at all, so nothing was being fed back to the GM. Whatever
contradiction rate they show is the rate for a GM working *unaided*, which is what a later
run with the ledger has to be compared against.

Two guards on the judge, in the tradition of the sweep's grounding check:

* it is only asked about facts that share substance with the passage, so the common case
  (a fact the passage simply does not mention) never reaches it;
* it must **quote the contradicting sentence verbatim**, and the quote is checked against
  the passage. A judge that cannot point at the text is not reporting a contradiction, it
  is producing one.

Nothing here writes to a campaign or to a session log. The report is the output.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Sequence

from dndc.analysis.replay import ReplayedSession
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, GMPromptBuilder, PartyMember, Turn
from dndc.gm.templates import render_template
from dndc.memory.canon_store import CanonStore, normalise
from dndc.memory.grounding import MIN_CONTENT_LEN, WORD, stem
from dndc.memory.sweep import SIMILAR_ENOUGH, CanonSweep, similarity
from dndc.models.base import GMBackend, GMBackendError, GMRequest, Message, Role

#: The judge answers in the `[[TAG:]]` form everything else in this project uses — the
#: sixth. `<fact number> | <quoted sentence> | <why>`.
CONTRADICTS_PATTERN = re.compile(
    r"\[\[\s*CONTRADICTS\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)

#: How much a fact and a passage must share before the judge is asked about them at all.
#: Low, because this is a *pre-filter* and not a decision: it exists to keep the judge
#: from being handed forty facts per turn, most of which the passage never touches. A
#: contradiction the filter drops is a contradiction phrased in entirely different words,
#: which is a real limitation and is reported as `skipped`.
RELEVANT_ENOUGH = 0.12

#: Most facts a passage shares words with still have nothing to do with it. Past this the
#: judge is reading a list rather than a question.
MAX_FACTS_PER_TURN = 12

#: Extraction, not prose. Same reasoning as the sweep's.
DRIFT_TEMPERATURE = 0.1

_NO_FACTS = "(nothing established yet)"


@dataclass(frozen=True)
class Contradiction:
    """One place the narration and the ledger cannot both be right."""

    turn: int
    entry_id: str
    fact: str
    #: The sentence from the narration, verified to actually be in it.
    quote: str
    note: str = ""

    def render(self) -> str:
        return f"turn {self.turn}: {self.fact!r} vs {self.quote!r} — {self.note}"


@dataclass
class DriftReport:
    """What one session says about whether the memory layers hold."""

    session_id: str | None = None
    campaign: str | None = None
    turns: int = 0
    #: Facts the GM declared inline. Zero for anything logged before P2.2 (2026-08-10).
    tagged: int = 0
    #: Facts recovered from the narration, with the turn each was first established on.
    established: list[tuple[int, CanonEntry]] = field(default_factory=list)
    #: Facts that reached the prompt a second session would send, and those that did not.
    survived: int = 0
    missing: list[str] = field(default_factory=list)

    contradictions: list[Contradiction] = field(default_factory=list)
    #: (turn, fact) pairs actually put to the judge, and pairs the pre-filter dropped.
    checked: int = 0
    skipped: int = 0
    #: Claimed contradictions thrown out because the quote was not in the passage.
    unquoted: int = 0

    calls: int = 0
    model: str | None = None
    duration_ms: int = 0
    error: str | None = None

    @property
    def ran(self) -> bool:
        return self.error is None

    @property
    def recovered(self) -> int:
        return len(self.established)

    @property
    def rate(self) -> float:
        """Contradictions per turn — the number the supersession decision needs."""
        return len(self.contradictions) / self.turns if self.turns else 0.0

    def summary(self) -> str:
        return (
            f"{self.turns} turns · {self.recovered} facts recovered "
            f"({self.tagged} tagged live) · {self.survived} survived, "
            f"{len(self.missing)} lost · {len(self.contradictions)} contradictions in "
            f"{self.checked} checks ({self.rate:.2f}/turn)"
        )


# --- survival: deterministic ------------------------------------------------


def recover(turns: Sequence[Turn], sweep: CanonSweep) -> list[tuple[int, CanonEntry]]:
    """Rebuild what a session established, turn by turn, with origins.

    Swept **one turn at a time** rather than in the sweep's usual eight-turn chunks. The
    sweep deliberately claims no turn number for what it finds (it read the whole session
    and does not know where a fact came from), but the contradiction scan needs to know
    which facts were standing *before* a given turn — so here the chunking supplies the
    provenance the sweep will not invent.

    Everything proposed is filed. There is no table in an analysis run, and a
    confirmation gate with nobody behind it is not a gate; what this measures is what the
    pipeline would have offered.
    """
    established: list[tuple[int, CanonEntry]] = []
    for index, turn in enumerate(turns):
        report = sweep.propose([turn])
        if not report.ran:
            break
        for proposal in report.proposals:
            entry = sweep.store.establish(
                proposal.text,
                scope=proposal.scope,
                established_by="drift replay",
            )
            # None means the ledger already holds it — an earlier turn established it,
            # and the earlier turn is the one that owns it.
            if entry is not None:
                established.append((index, entry))
    return established


def survives(ledger: CanonLedger, party: Sequence[str] = ()) -> tuple[int, list[str]]:
    """How much of a ledger reaches the prompt a fresh session would send.

    Built through the real `GMPromptBuilder`, not by reading the ledger back — the
    question is whether the *prompt* carries the world, and a test that inspects the
    ledger it just wrote would pass with the builder disconnected entirely. That is the
    failure D-002 exists to prevent and the one most likely to happen silently.
    """
    context = CampaignContext(
        name="drift check",
        party=[PartyMember(name=name, player="replay") for name in party],
        ledger=ledger,
    )
    state = GMPromptBuilder().campaign_state(context)
    flattened = " ".join(state.split())

    survived = 0
    missing = []
    for entry in ledger.active():
        if " ".join(entry.text.split()) in flattened:
            survived += 1
        else:
            missing.append(entry.text)
    return survived, missing


# --- contradiction: model-assisted ------------------------------------------


class ContradictionScan:
    """Asks the batch seat whether narration conflicts with standing canon."""

    def __init__(
        self,
        backend: GMBackend,
        max_tokens: int = 512,
        relevance: float = RELEVANT_ENOUGH,
        max_facts: int = MAX_FACTS_PER_TURN,
    ) -> None:
        self.backend = backend
        self.max_tokens = max_tokens
        self.relevance = relevance
        self.max_facts = max_facts

    def scan(
        self,
        turns: Sequence[Turn],
        established: Sequence[tuple[int, CanonEntry]],
        report: DriftReport,
    ) -> list[Contradiction]:
        """Every turn against the facts that were standing when it was narrated."""
        found: list[Contradiction] = []
        for index, turn in enumerate(turns):
            standing = [entry for origin, entry in established if origin < index]
            if not standing:
                continue

            relevant, skipped = self._relevant(turn.narration, standing)
            report.skipped += skipped
            if not relevant:
                continue

            report.checked += len(relevant)
            answer = self._ask(turn.narration, relevant, report)
            if answer is None:
                break
            found.extend(self._parse(answer, index, turn.narration, relevant, report))
        return found

    def _relevant(
        self, narration: str, standing: Sequence[CanonEntry]
    ) -> tuple[list[CanonEntry], int]:
        """Facts worth asking about, and how many were dropped unasked."""
        passage = _content_words(narration)
        scored = []
        for entry in standing:
            overlap = _overlap(_content_words(entry.text), passage)
            if overlap >= self.relevance:
                scored.append((overlap, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        kept = [entry for _, entry in scored[: self.max_facts]]
        return kept, len(standing) - len(kept)

    def _ask(
        self, narration: str, facts: Sequence[CanonEntry], report: DriftReport
    ) -> str | None:
        request = GMRequest(
            system=render_template("drift_check", facts=_numbered(facts)),
            messages=(Message(role=Role.USER, content=narration),),
            max_tokens=self.max_tokens,
            cache_system=False,
        )
        try:
            response = self.backend.generate(request)
        except GMBackendError as exc:
            report.error = str(exc)
            return None
        except Exception as exc:  # a local box that went away mid-scan
            report.error = f"{type(exc).__name__}: {exc}"
            return None

        report.calls += 1
        report.model = response.model
        return "" if response.refused else response.text

    def _parse(
        self,
        text: str,
        turn: int,
        narration: str,
        facts: Sequence[CanonEntry],
        report: DriftReport,
    ) -> list[Contradiction]:
        """Claims the judge could point at. The rest are counted and dropped."""
        passage = " ".join(narration.split()).casefold()
        found = []
        for match in CONTRADICTS_PATTERN.finditer(text):
            parts = [part.strip() for part in match.group("body").split("|")]
            if len(parts) < 2:
                report.unquoted += 1
                continue

            index = _fact_number(parts[0])
            quote = " ".join(parts[1].split())
            if index is None or not 1 <= index <= len(facts) or not quote:
                report.unquoted += 1
                continue
            # The guard the sweep's second live run taught: a claim that cannot be found
            # in its source is the model writing, not reading.
            if quote.strip('"“”').casefold() not in passage:
                report.unquoted += 1
                continue

            entry = facts[index - 1]
            found.append(
                Contradiction(
                    turn=turn,
                    entry_id=entry.id,
                    fact=entry.text,
                    quote=quote,
                    note=parts[2] if len(parts) > 2 else "",
                )
            )
        return found


# --- the whole instrument ---------------------------------------------------


def measure(
    session: ReplayedSession,
    sweep: CanonSweep,
    scan: ContradictionScan | None = None,
) -> DriftReport:
    """Replay a session's world, check it survives, and count what contradicted it."""
    report = DriftReport(
        session_id=session.session_id,
        campaign=session.campaign,
        turns=len(session.turns),
        tagged=len(session.tagged),
    )
    if not session.turns:
        return report

    started = time.monotonic()
    report.established = recover(session.turns, sweep)
    report.survived, report.missing = survives(sweep.store.ledger, session.party)
    if scan is not None:
        report.contradictions = scan.scan(session.turns, report.established, report)
    report.duration_ms = int((time.monotonic() - started) * 1000)
    return report


@dataclass
class StabilityReport:
    """How much of a committed baseline a fresh sweep of the same log finds again.

    A measurement of the *model*, not of us. It is expected to move — the whole reason
    the baseline is a file rather than a seed — and reporting it as its own number is
    what stops that movement from contaminating the survival check (Fable, 2026-08-15).
    """

    baseline: int = 0
    recovered: int = 0
    #: Baseline facts found again word for word, and found again in different words.
    identical: int = 0
    equivalent: int = 0
    #: Baseline facts this run did not find, and facts this run found that are not in it.
    lost: list[str] = field(default_factory=list)
    gained: list[str] = field(default_factory=list)

    @property
    def stability(self) -> float:
        """Share of the baseline recovered again, counting a reworded match."""
        found = self.identical + self.equivalent
        return found / self.baseline if self.baseline else 0.0

    def summary(self) -> str:
        return (
            f"{self.baseline} in the baseline · {self.recovered} recovered now · "
            f"{self.identical} identical, {self.equivalent} reworded, "
            f"{len(self.lost)} missed, {len(self.gained)} new "
            f"({self.stability:.0%} stable)"
        )


def compare(
    baseline: Sequence[CanonEntry],
    recovered: Sequence[CanonEntry],
    threshold: float = SIMILAR_ENOUGH,
) -> StabilityReport:
    """Diff a fresh recovery against a committed baseline.

    Two readings, both reported, because they answer different questions. *Identical* is
    whether the model said the same words; *equivalent* is whether it found the same
    fact. A sweep that recovers everything in fresh phrasing is stable in the way that
    matters and unstable in the way a string comparison can see, and collapsing those
    into one number would hide which happened.
    """
    report = StabilityReport(baseline=len(baseline), recovered=len(recovered))
    remaining = list(recovered)

    for entry in baseline:
        exact = next(
            (o for o in remaining if normalise(o.text) == normalise(entry.text)), None
        )
        if exact is not None:
            remaining.remove(exact)
            report.identical += 1
            continue

        close = max(
            remaining, key=lambda o: similarity(entry.text, o.text), default=None
        )
        if close is not None and similarity(entry.text, close.text) >= threshold:
            remaining.remove(close)
            report.equivalent += 1
            continue
        report.lost.append(entry.text)

    report.gained = [entry.text for entry in remaining]
    return report


def store_for_replay(log=None) -> CanonStore:
    """A fresh in-memory ledger. An analysis run never touches a campaign's file."""
    return CanonStore(CanonLedger(), log=log)


def _numbered(facts: Sequence[CanonEntry]) -> str:
    if not facts:
        return _NO_FACTS
    return "\n".join(f"{index}. {entry.text}" for index, entry in enumerate(facts, start=1))


def _fact_number(text: str) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in (stem(match) for match in WORD.findall(text))
        if len(word) >= MIN_CONTENT_LEN
    }


def _overlap(fact: set[str], passage: set[str]) -> float:
    """What share of the fact's substance the passage also uses.

    Containment rather than Jaccard: a fact is one sentence and a passage is two hundred
    words, so symmetric similarity would score every real pair near zero.
    """
    if not fact:
        return 0.0
    return len(fact & passage) / len(fact)


#: Re-exported so a caller need not reach into `gm.canon` to read a report.
__all__ = [
    "CanonScope",
    "Contradiction",
    "ContradictionScan",
    "DriftReport",
    "StabilityReport",
    "compare",
    "measure",
    "recover",
    "store_for_replay",
    "survives",
]
