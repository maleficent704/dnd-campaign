"""Stance-scoped supersession (P4.6) — the mystery's OD-13, ported to a game with beliefs.

Until now the GM could only *add* to what a character thinks. Convince the caravan guard
the teamster is innocent and the ledger gains a second belief beside the first; next turn
his prompt carries both, the gatekeeper licenses both (each is "their own belief, which may
be wrong"), and the 70B says whichever it reaches. That is the quiet contradiction the
mystery named: a lie that stays in force until some later reply happens to touch it, by
which time the table has already heard the character hold two stories at once.

The mystery's answer is to judge the **whole** standing set against the newly authorized
one at the moment it changes, and retire what it replaces before anything can be said from
it. This module is that judgement.

Three properties, two of them inherited from the gatekeeper and one that is this pass's
own:

**It fails open by retiring nothing.** A dead host, an unparseable verdict, no judge
configured at all — the ledger is left exactly as it was, which is the behaviour every
phase up to now has had. A broken judge costs the improvement, never the campaign.

**The two directions are not symmetric, and the prompt says so.** A belief kept in error
is audible — the character says something that no longer fits, and the table notices. A
belief retired in error vanishes from every future prompt and nobody ever notices. So the
benefit of the doubt runs one way: when unsure, keep.

**It is told beliefs and nothing else.** No canon, no `gm_only`, no voice card. A
character's own beliefs are already theirs, so unlike the gatekeeper's draft there is not
even untrusted text in this call — but the same rule holds for the same reason: the plot
does not enter a second model call to save a round trip.

Numbers, not ids. The judge answers with positions in a list rather than entry ids like
`belief-guard-teamster`, because a 70B handed an id will eventually return a plausible
variant of one, and a hallucinated id is indistinguishable from a real one until it fails
to match. A number out of range is simply dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from dndc.gm.canon import CanonEntry
from dndc.gm.templates import render_template
from dndc.models.base import GMBackend, GMRequest, GMResponse, Message, Role

#: One retry on malformed output, then fail open — the gatekeeper's number, for the same
#: reason: a second retry has never produced valid JSON where the first did not.
MAX_PARSE_RETRIES = 1

#: A verdict is a short JSON object: a list of small integers and a phrase.
MAX_TOKENS = 200

#: Judgement wants no creativity. The same change of mind should retire the same beliefs
#: twice, or the ledger depends on a sampler.
TEMPERATURE = 0.0

_RETRY = (
    "That was not valid JSON matching the contract. Error:\n{error}\n\n"
    "Return only the object, with keys retire and reason."
)


class _Retirement(BaseModel):
    """One retirement, with the words it claims are contradicted.

    The quote is the whole mechanism. "When unsure, keep" is unenforceable advice on its
    own — a model that is vaguely unsure retires anyway — but a judge that has to point at
    the contradicted words cannot retire on relatedness, because there are no words to
    point at. It is the gatekeeper's "read every sentence" discipline moved out of the
    prose and into the output contract, where it can be checked.
    """

    model_config = ConfigDict(extra="forbid")

    number: int
    contradicts: str = ""


class _Response(BaseModel):
    """The JSON contract. Strict, because a judge that drifts its output format is a
    judge that silently stops judging — and this one fails open, so it would go quiet."""

    model_config = ConfigDict(extra="forbid")

    retire: list[_Retirement | int] = []
    reason: str = ""


@dataclass(frozen=True)
class StanceJudgement:
    """What a change of mind retired. `judged` is False on every fail-open path."""

    #: The entries superseded, in the order they stood in the ledger.
    retired: tuple[CanonEntry, ...] = ()
    #: Everything that was put to the judge, retired or not. `considered` minus `retired`
    #: is what it saw and left standing — the difference between a conservative judge and
    #: an absent one, and the reason this is recorded at all.
    considered: tuple[CanonEntry, ...] = ()
    judged: bool = True
    reason: str = ""
    #: Every judge call this verdict took, in order — including the retry that failed to
    #: parse. Kept whole rather than as text so the caller can bill the seat and record
    #: the latency: the table waits on this call, and a wait nobody logged is the mistake
    #: `cost.latency_ms` was added to stop repeating (D-008 item 23).
    responses: tuple[GMResponse, ...] = ()
    model: str | None = None
    call_id: str | None = None

    @property
    def raw(self) -> tuple[str, ...]:
        return tuple(response.text for response in self.responses)

    @property
    def kept(self) -> tuple[CanonEntry, ...]:
        retired = {entry.id for entry in self.retired}
        return tuple(entry for entry in self.considered if entry.id not in retired)


@dataclass
class StanceJudge:
    """Decides which standing beliefs a new one replaces, on whatever seat it is given."""

    backend: GMBackend
    max_tokens: int = MAX_TOKENS
    retries: int = MAX_PARSE_RETRIES

    def judge(
        self, name: str, belief: str, standing: Sequence[CanonEntry]
    ) -> StanceJudgement:
        """Never raises — every failure path ends in `judged=False`, retiring nothing."""
        standing = tuple(standing)
        if not standing or not belief.strip():
            # Nothing to weigh. Not a failure, and not worth a call: a character with no
            # standing beliefs has changed their mind about nothing.
            return StanceJudgement(considered=standing)

        messages: list[Message] = [
            Message(role=Role.USER, content=f"Now: {belief.strip()}")
        ]
        system = render_template(
            "stance",
            name=name,
            belief=belief.strip(),
            standing=render_standing(standing),
        )
        seen: list[GMResponse] = []
        model: str | None = None

        for attempt in range(self.retries + 1):
            try:
                response = self.backend.generate(
                    GMRequest(
                        system=system,
                        messages=tuple(messages),
                        max_tokens=self.max_tokens,
                    )
                )
            except Exception as exc:  # unreachable host, timeout, anything at all
                return self._unjudged(standing, f"{type(exc).__name__}: {exc}", seen, model)

            seen.append(response)
            model = response.model
            try:
                parsed = _parse(response.text)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                if attempt >= self.retries:
                    return self._unjudged(
                        standing, f"unparseable verdict: {exc}", seen, model
                    )
                messages = [
                    *messages,
                    Message(role=Role.ASSISTANT, content=response.text),
                    Message(role=Role.USER, content=_RETRY.format(error=exc)),
                ]
                continue

            return StanceJudgement(
                retired=_pick(standing, parsed.retire),
                considered=standing,
                judged=True,
                reason=parsed.reason.strip(),
                responses=tuple(seen),
                model=model,
                call_id=response.call_id,
            )

        return self._unjudged(standing, "no verdict", seen, model)  # unreachable

    def _unjudged(
        self,
        standing: tuple[CanonEntry, ...],
        reason: str,
        seen: list[GMResponse],
        model: str | None,
    ) -> StanceJudgement:
        """Fail open: nothing is retired, and the log says nobody judged it."""
        return StanceJudgement(
            retired=(),
            considered=standing,
            judged=False,
            reason=reason,
            responses=tuple(seen),
            model=model,
        )


def render_standing(entries: Sequence[CanonEntry]) -> str:
    """A numbered list, one belief per line. The numbers are the answer format."""
    return "\n".join(f"{index}. {entry.text}" for index, entry in enumerate(entries, 1))


def _pick(
    standing: Sequence[CanonEntry], chosen: Sequence[object]
) -> tuple[CanonEntry, ...]:
    """Positions to entries, dropping anything out of range, any repeat, and any
    retirement that could not say what it contradicts.

    Out of range is not an error worth failing the pass over: a judge that answers `[2, 7]`
    against a list of three has got one right, and discarding the 2 to punish the 7 would
    lose a correct retirement to a formatting slip. Order follows the ledger, not the
    judge's, so the log reads the same way the prompt did.

    **An unquoted retirement is dropped**, and a bare number is unquoted. That is the
    fail-safe direction — keeping a belief is recoverable and losing one is not — and it is
    self-policing: a judge that stops quoting stops retiring, and the control notices on
    the next run rather than the ledger quietly emptying over a campaign.
    """
    wanted: set[int] = set()
    for item in chosen:
        number = item.number if isinstance(item, _Retirement) else item
        quoted = isinstance(item, _Retirement) and bool(item.contradicts.strip())
        if quoted and 1 <= number <= len(standing):
            wanted.add(number)
    return tuple(standing[number - 1] for number in sorted(wanted))


def _parse(text: str) -> _Response:
    return _Response.model_validate(json.loads(_extract_json(text)))


def _extract_json(text: str) -> str:
    """Pull the object out of whatever wrapping a local model put round it."""
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = parts[1] if len(parts) >= 2 else stripped.strip("`")
        if stripped.lstrip().casefold().startswith("json"):
            stripped = stripped.lstrip()[4:]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in judge reply: {text[:120]!r}")
    return stripped[start : end + 1]


# --- the positive control --------------------------------------------------


@dataclass(frozen=True)
class StanceCase:
    """One change of mind, and which of the standing beliefs must go.

    Written as belief *text*, not ids, so a case survives the ledger being re-minted and
    reads as a scene rather than as a fixture.
    """

    #: What the character now believes.
    belief: str
    #: The standing beliefs a working pass must retire, matched on exact text.
    retires: tuple[str, ...] = ()
    note: str = ""


@dataclass
class StanceReport:
    """Recall and false retirements — the P2.6 discipline, applied to supersession.

    Two numbers, and the second is the one that would hurt. A pass that retires nothing is
    the old behaviour and merely useless; a pass that retires the wrong belief deletes
    something a character thinks, silently, for the rest of the campaign.
    """

    retired: int = 0
    should_retire: int = 0
    false_retirements: int = 0
    kept: int = 0
    misses: list[tuple[StanceCase, str]] = field(default_factory=list)
    overreach: list[tuple[StanceCase, str]] = field(default_factory=list)
    unjudged: int = 0

    @property
    def trustworthy(self) -> bool:
        return (
            self.retired == self.should_retire
            and self.false_retirements == 0
            and self.unjudged == 0
        )

    def summary(self) -> str:
        return (
            f"retired {self.retired}/{self.should_retire} it should, "
            f"{self.false_retirements}/{self.kept} it should not"
        )


def run_stance_control(
    judge: StanceJudge,
    name: str,
    standing: Sequence[CanonEntry],
    cases: Sequence[StanceCase],
) -> StanceReport:
    """Run planted changes of mind past the judge and score it.

    The P2.6 rule again — *a zero is also what a broken instrument produces* — and here
    the zero is especially easy to produce, because the pass fails open. "Nothing was
    retired tonight" is what a correct conservative judge, a wrong one, and an unreachable
    host all look like from the log, unless something has proved the judge retires what is
    definitely incompatible and leaves alone what definitely is not.
    """
    report = StanceReport()
    for case in cases:
        judgement = judge.judge(name, case.belief, standing)
        if not judgement.judged:
            report.unjudged += 1
        retired = {entry.text.strip() for entry in judgement.retired}
        expected = {text.strip() for text in case.retires}
        for text in expected:
            report.should_retire += 1
            if text in retired:
                report.retired += 1
            else:
                report.misses.append((case, text))
        for entry in judgement.considered:
            if entry.text.strip() in expected:
                continue
            report.kept += 1
            if entry.text.strip() in retired:
                report.false_retirements += 1
                report.overreach.append((case, entry.text.strip()))
    return report


__all__ = [
    "MAX_PARSE_RETRIES",
    "MAX_TOKENS",
    "TEMPERATURE",
    "StanceCase",
    "StanceJudge",
    "StanceJudgement",
    "StanceReport",
    "render_standing",
    "run_stance_control",
]
