"""The "previously on…" (P5.3) — the campaign's record, read back to the players.

The chronicle already writes a paragraph per session. This is not that paragraph. A
chronicle entry is written **for the GM's prompt**: it is stored, it enters every later
call, and it is phrased as a record. A recap is written **for Kelly and Sam**, out loud,
in the half-minute before the first turn, and it is kept nowhere at all — it is generated
fresh each time the campaign is picked up and thrown away when it has been read.

Three properties, in the order they matter.

**It writes no canon.** The recapper is handed no store and has nothing to write with, so
the read-only rule is a fact about the object rather than a line in a prompt. A recap that
could file canon would be a fourth memory layer nobody ratified — and the worst of the
four, since it is the only one summarising summaries rather than play.

**It is never told anything the players do not know.** The caller passes the chronicle and
`player_known` canon and nothing else; `gm_only` facts never reach this call. That is the
P4.1 discipline applied to a second surface: the protection is what is absent from the
prompt, not an instruction to keep a secret. A recap read aloud from the GM's own notes
would spoil a campaign faster than any NPC could.

**It is grounded, and it fails to nothing.** The same check the sweep and the chronicle
use (`memory/grounding.py`): a recap naming somebody the record never mentioned is
rejected, retried once with the offending names, and then skipped. Like both of those, it
never raises — an evening must not fail to start because the GPU box is asleep.

It also carries a proposal the record cannot otherwise make. `campaign.scene` — where the
party is standing — is written only by `--scene` and `/scene`, so a party that travelled
last session picks up wherever a human last remembered to type. The recap has just read
the record, so it says where it thinks they are, in one sentence, and the table confirms
it before anything uses it. Rejecting it changes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from dndc.gm.chronicle import Chronicle
from dndc.gm.templates import render_template
from dndc.logging import SessionLog
from dndc.memory.grounding import unknown_names, vocabulary
from dndc.memory.sweep import LOCAL_BILLING
from dndc.models import BATCH_SEAT
from dndc.models.base import GMBackend, GMBackendError, GMRequest, Message, Role
from dndc.schema.events import Cost, Recap, RecapStatus

#: `gm/prompts/recap.md`.
TEMPLATE = "recap"

#: Four to six sentences and a scene line. Room to finish a thought, not room to ramble.
MAX_TOKENS = 400

#: Reporting, not writing: two different recaps of the same evening would both be suspect.
RECAP_TEMPERATURE = 0.0

#: What the prompt says to write when the record does not say where the party ended up.
#: Taken literally: a scene proposal is only worth having when it is worth having.
NO_SCENE = "unknown"

_PREVIOUSLY = re.compile(r"^\W*previously\W*:?\s*", re.IGNORECASE)
_WHERE = re.compile(r"^\W*where\W*:?\s*", re.IGNORECASE)


@dataclass
class RecapReport:
    """What one pickup produced, whether or not anything was shown."""

    text: str = ""
    #: Where the recap thinks the party is standing. `None` when it would not say.
    scene: str | None = None
    #: Set by whoever asked the table. Part of what happened, so the row waits for it.
    scene_accepted: bool = False
    covers: tuple[str, ...] = ()
    status: RecapStatus = RecapStatus.SKIPPED
    invented: list[str] = field(default_factory=list)
    calls: int = 0
    model: str | None = None
    call_id: str | None = None
    duration_ms: int | None = None
    error: str | None = None

    @property
    def shown(self) -> bool:
        return bool(self.text)


class Recapper:
    """Reads the campaign's own record back to the table. Writes nothing to it."""

    def __init__(
        self,
        backend: GMBackend,
        log: SessionLog | None = None,
        party: Sequence[str] = (),
        max_tokens: int = MAX_TOKENS,
        seat: str = BATCH_SEAT,
    ) -> None:
        self.backend = backend
        self.log = log
        self.party = list(party)
        self.max_tokens = max_tokens
        self.seat = seat

    def recap(self, campaign: str, chronicle: Chronicle, known: Sequence[str] = ()) -> RecapReport:
        """Read the record and write the pickup. Never raises.

        `known` is what the players already know — `player_known` canon, filtered by the
        caller. Nothing else about the world reaches this call.
        """
        covers = tuple(
            session for entry in chronicle.entries for session in (entry.sessions or (entry.id,))
        )
        report = RecapReport(covers=covers)
        source = self._source(chronicle, known)
        if not source.strip():
            # A campaign with no record yet. There is nothing to be reminded of, and a
            # model asked to recap nothing will happily invent an evening.
            return report

        correction = ""
        for _ in range(2):
            text = self._call(report, campaign, source, correction)
            if text is None:
                return report

            previously, scene = _split(text)
            if not previously:
                return report

            invented = unknown_names(previously, self._known(source))
            if invented:
                report.invented = invented
                report.status = RecapStatus.UNGROUNDED
                correction = ", ".join(invented)
                continue

            report.text = previously
            report.scene = scene
            report.invented = []
            report.status = RecapStatus.WRITTEN
            return report
        return report

    def record(self, report: RecapReport) -> Recap | None:
        """Log what the table was shown, and what they did with the scene proposal.

        Emitted after they have answered rather than at the end of the call, because
        `scene_accepted` is part of what happened and a written log line is never
        rewritten.
        """
        if self.log is None:
            return None
        return self.log.emit(
            Recap,
            text=report.text,
            scene=report.scene,
            scene_accepted=report.scene_accepted,
            covers=report.covers,
            status=report.status,
            invented=tuple(report.invented),
            model=report.model,
            call_id=report.call_id,
        )

    # --- one call -----------------------------------------------------------

    def _call(
        self, report: RecapReport, campaign: str, source: str, correction: str
    ) -> str | None:
        request = GMRequest(
            system=render_template(
                TEMPLATE,
                campaign=campaign or "this campaign",
                party=self._party(),
                correction=_correction(correction),
            ),
            messages=(Message(role=Role.USER, content=source),),
            max_tokens=self.max_tokens,
            # One call per pickup, and the record differs every time.
            cache_system=False,
        )
        try:
            response = self.backend.generate(request)
        except GMBackendError as exc:
            report.error = str(exc)
            return None
        except Exception as exc:  # a local box that went away between sessions
            report.error = f"{type(exc).__name__}: {exc}"
            return None

        report.calls += 1
        report.model = response.model
        report.call_id = response.call_id
        report.duration_ms = response.duration_ms
        self._emit_cost(response)
        if response.refused or not response.text.strip():
            return None
        return response.text

    def _source(self, chronicle: Chronicle, known: Sequence[str]) -> str:
        parts: list[str] = []
        if chronicle.entries:
            parts.append("## The campaign so far, oldest first")
            for entry in chronicle.entries:
                when = f" ({entry.created})" if entry.created else ""
                parts.append(f"### Session {', '.join(entry.sessions) or entry.id}{when}\n"
                             f"{entry.render()}")
        facts = [fact for fact in known if fact.strip()]
        if facts:
            parts.append("## What the party knows")
            parts.extend(f"- {fact}" for fact in facts)
        return "\n\n".join(parts)

    def _known(self, source: str) -> set[str]:
        """What the recap may name: whatever the record did, plus the party's own names."""
        known = vocabulary(source)
        for name in self.party:
            known |= vocabulary(name)
        return known

    def _party(self) -> str:
        return "\n".join(f"- {name}" for name in self.party) or "- (unnamed)"

    def _emit_cost(self, response) -> None:
        if self.log is None:
            return
        usage = response.usage
        self.log.emit(
            Cost,
            seat=self.seat,
            model=response.model,
            billing=LOCAL_BILLING,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            latency_ms=response.duration_ms,
            call_id=response.call_id,
        )


def _split(text: str) -> tuple[str, str | None]:
    """`PREVIOUSLY:` and `WHERE:` out of a reply, tolerantly.

    A model that answers with only prose has still said something worth showing, so an
    unlabelled reply becomes the recap with no scene proposal. The asymmetry is on
    purpose: prose the table did not need costs them ten seconds, and a scene sentence
    picked out of the wrong place would start the evening in the wrong room.
    """
    previously: list[str] = []
    where: list[str] = []
    target = previously
    labelled = False

    for line in text.strip().splitlines():
        stripped = line.strip().strip("`")
        if _PREVIOUSLY.match(stripped):
            target = previously
            labelled = True
            stripped = _PREVIOUSLY.sub("", stripped)
        elif _WHERE.match(stripped):
            target = where
            labelled = True
            stripped = _WHERE.sub("", stripped)
        if stripped:
            target.append(stripped)

    if not labelled:
        return _tidy(text), None
    scene = _tidy(" ".join(where))
    if not scene or scene.casefold().rstrip(".") == NO_SCENE:
        scene = ""
    return _tidy(" ".join(previously)), (scene or None)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text.strip())
    return re.sub(r"\n{3,}", "\n\n", text)


def _correction(names: str) -> str:
    if not names:
        return ""
    return (
        f"\nYour last attempt named {names}, which the record does not mention. "
        f"Write only about what is below.\n"
    )
