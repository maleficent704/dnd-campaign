"""The NPC output gate (P4.4, D-003) — a backstop, not the gate.

The architecture is what protects: an NPC's prompt is built from what that character knows,
so a secret is safe because it was never assembled in (P4.1/P4.2). This layer measures how
well that holds, and repairs the one failure absence cannot prevent — **fabrication**. A
model that was told nothing about the salt sheds can still invent something about them, and
a player who asserts a secret can still be agreed with.

Three properties, all of them the mystery's and all of them load-bearing:

**It fails open.** Unreachable host, unparseable output twice running, a timeout — the draft
is shown and the verdict is logged as `unchecked`. A broken checker must never break a turn:
the tiered architecture is the protection, and a backstop that can halt play is worse than
no backstop. `unchecked` exists rather than reusing `pass` for the same reason
`gatekeeper_verdict` stayed `None` before there was a gate at all — a row claiming a check
succeeded when none ran is worse than one that says nothing, because it gets believed.

**The raw draft is always kept.** Pre-censor drafts are the denominator of every leak rate
Phase 7 will compute. A gate that quietly improved the record of its own performance would
be an instrument measuring itself.

**The gatekeeper never sees the secret either** — and this is where it departs from the
mystery, deliberately. There, the gatekeeper is the director and holds the withheld truth,
because suspects genuinely know their own secrets and the check is about tier discipline.
Here the NPC prompt never contained `gm_only` canon in the first place, so a leak can only
arise by invention or by agreement. Asking "does this draft assert anything outside what the
character knows?" catches both **without the secret ever entering a second model call** —
which matters, because the draft is untrusted text and a checker that holds the plot is a
checker worth prompt-injecting.

The line this draws on invention is mechanical, and it is the answer to the question the
first live session raised: feelings, opinions, weather and vague personal history are the
character's own; **a specific person, place, time, object or event that is not on their list
is not**, and naming one the travellers have just raised is the common failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from dndc.gm.canon import CanonLedger, CanonScope
from dndc.gm.templates import render_template
from dndc.models.base import GMBackend, GMRequest, Message, Role
from dndc.schema.npc import NPC

#: One retry on malformed output, then fail open. A second retry has never once produced
#: valid JSON where the first did not, and it doubles the latency the table is waiting on.
MAX_PARSE_RETRIES = 1

#: A verdict is a short JSON object. This is generous for one, and mean enough that a
#: checker which starts narrating gets cut off rather than billed for.
MAX_TOKENS = 300

#: Judgement wants no creativity — the same draft should get the same verdict twice.
TEMPERATURE = 0.0

_RETRY = (
    "That was not valid JSON matching the contract. Error:\n{error}\n\n"
    'Return only the object, with keys verdict, reason and rewrite.'
)


class Verdict(str, Enum):
    """What happened to a draft. Written to `npc_turn.gatekeeper_verdict` (D-008 item 19)."""

    #: Checked and clean.
    PASS = "pass"
    #: Checked, found wanting, and the rewrite was shown instead.
    REVISED = "revised"
    #: Checked, found wanting, and no usable rewrite came back — nothing was shown.
    BLOCKED = "blocked"
    #: The check could not be made. The draft was shown anyway; this is the fail-open row.
    UNCHECKED = "unchecked"


class _Response(BaseModel):
    """The JSON contract. Strict, because a checker that drifts its own output format is
    a checker that silently stops checking."""

    model_config = ConfigDict(extra="forbid")

    verdict: str
    reason: str = ""
    rewrite: str | None = None


@dataclass(frozen=True)
class Judgement:
    """One draft, judged. `text` is what the table should see."""

    verdict: Verdict
    #: What to display: the draft when it passed or could not be checked, the rewrite when
    #: it was revised, and nothing at all when it was blocked.
    text: str
    #: What the model actually said, always, whatever the verdict.
    draft: str
    reason: str = ""
    #: Raw checker replies, in order — kept for the same reason the draft is.
    raw: tuple[str, ...] = ()

    @property
    def intercepted(self) -> bool:
        return self.verdict in (Verdict.REVISED, Verdict.BLOCKED)


@dataclass
class Gatekeeper:
    """Checks NPC drafts on whatever seat it is given."""

    backend: GMBackend
    max_tokens: int = MAX_TOKENS
    retries: int = MAX_PARSE_RETRIES

    def check(self, npc: NPC, ledger: CanonLedger, draft: str) -> Judgement:
        """Judge one line. Never raises — every failure path ends in `unchecked`."""
        if not draft.strip():
            # Nothing to check, and nothing to show. Not a failure of the gate.
            return Judgement(verdict=Verdict.PASS, text="", draft=draft)

        messages: list[Message] = [
            Message(role=Role.USER, content=f"Draft: {draft.strip()}")
        ]
        system = render_template(
            "gatekeeper", name=npc.name, knowledge=_knowledge(npc, ledger)
        )
        raw: list[str] = []

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
                return self._unchecked(draft, f"{type(exc).__name__}: {exc}", raw)

            raw.append(response.text)
            try:
                parsed = _parse(response.text)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                if attempt >= self.retries:
                    return self._unchecked(draft, f"unparseable verdict: {exc}", raw)
                messages = [
                    *messages,
                    Message(role=Role.ASSISTANT, content=response.text),
                    Message(role=Role.USER, content=_RETRY.format(error=exc)),
                ]
                continue

            return self._judge(draft, parsed, raw)

        return self._unchecked(draft, "no verdict", raw)  # unreachable, kept for clarity

    # --- outcomes ----------------------------------------------------------

    def _judge(self, draft: str, parsed: _Response, raw: list[str]) -> Judgement:
        if parsed.verdict.strip().casefold() in {"pass", "clean", "ok"}:
            return Judgement(Verdict.PASS, text=draft, draft=draft, raw=tuple(raw))

        rewrite = (parsed.rewrite or "").strip()
        if not rewrite:
            # Asked for a repair and given none. Blocking is the conservative reading:
            # the checker found something and could not fix it, so showing the draft
            # anyway would make the interception meaningless.
            return Judgement(
                Verdict.BLOCKED, text="", draft=draft, reason=parsed.reason, raw=tuple(raw)
            )
        return Judgement(
            Verdict.REVISED, text=rewrite, draft=draft, reason=parsed.reason, raw=tuple(raw)
        )

    def _unchecked(self, draft: str, reason: str, raw: list[str]) -> Judgement:
        """Fail open: show the draft, and say in the log that nothing checked it."""
        return Judgement(
            Verdict.UNCHECKED, text=draft, draft=draft, reason=reason, raw=tuple(raw)
        )


def _knowledge(npc: NPC, ledger: CanonLedger) -> str:
    """The same view the NPC's own prompt was built from — `for_npc`, never `active`.

    If these two ever diverge the gate becomes noise: judging a draft against a different
    list than the one that produced it would flag every legitimate line and miss the
    invented ones.
    """
    permitted = ledger.for_npc(npc)
    if not permitted:
        return "- (nothing at all — this character knows no facts)"
    lines = []
    for entry in permitted:
        marker = " (their own belief, which may be wrong)" if entry.scope is CanonScope.NPC_BELIEF else ""
        lines.append(f"- {entry.text}{marker}")
    return "\n".join(lines)


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
        raise ValueError(f"no JSON object in checker reply: {text[:120]!r}")
    return stripped[start : end + 1]


# --- the positive control --------------------------------------------------


@dataclass(frozen=True)
class ControlCase:
    """One planted draft, and whether a working gate must intercept it."""

    draft: str
    #: True when this draft asserts something the character cannot know.
    invents: bool
    note: str = ""


@dataclass
class ControlReport:
    """Recall and false positives — what makes a later zero believable (the P2.6 rule)."""

    caught: int = 0
    planted: int = 0
    false_positives: int = 0
    clean: int = 0
    misses: list[ControlCase] = field(default_factory=list)
    flagged: list[tuple[ControlCase, str]] = field(default_factory=list)

    @property
    def trustworthy(self) -> bool:
        """Every planted invention caught, nothing clean flagged. Anything less and a
        zero from this gate means nothing in particular."""
        return self.caught == self.planted and self.false_positives == 0

    def summary(self) -> str:
        return (
            f"caught {self.caught}/{self.planted} planted, "
            f"{self.false_positives}/{self.clean} false positives"
        )


def run_control(
    gate: Gatekeeper, npc: NPC, ledger: CanonLedger, cases: Sequence[ControlCase]
) -> ControlReport:
    """Run planted drafts past the gate and score it.

    The P2.6 discipline, one layer up: **a zero is also what a broken instrument produces.**
    Before trusting "no leaks were caught tonight" as evidence about the NPC tier, prove the
    checker catches leaks that are definitely there — and, just as important, that it leaves
    clean lines alone, because a gate that rewrites everything protects nothing and ruins
    every voice in the campaign.
    """
    report = ControlReport()
    for case in cases:
        judgement = gate.check(npc, ledger, case.draft)
        if case.invents:
            report.planted += 1
            if judgement.intercepted:
                report.caught += 1
            else:
                report.misses.append(case)
        else:
            report.clean += 1
            if judgement.intercepted:
                report.false_positives += 1
                report.flagged.append((case, judgement.reason))
    return report
