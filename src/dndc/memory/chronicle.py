"""Writing the campaign chronicle (P2.5) — D-002's compression job.

At the end of a session the batch utility seat reads the session back and writes a
paragraph: what happened, what changed, what was left hanging. That paragraph goes into
every later session's prompt, which is how session nine's GM knows about session two
without carrying session two's transcript. D-002's prompt rule — rebuilt from ledger + chronicle + window,
never from a growing transcript — is only affordable because this layer exists.

It runs in the same slot as the P2.3 sweep, immediately after it, and inherits that task's
posture with two deliberate differences.

**Inherited: the summary must come from the session.** A live run of the sweep had
`llama3.1:8b` answer with the prompt's own worked examples, naming a person who was not in
the transcript. The same guard applies here (`memory/grounding.py`): a summary naming
someone the session never mentioned is rejected, retried once, and then skipped. **No
chronicle entry is strictly better than a fabricated one** — the ledger still holds the
facts, the window still holds the last turns, and the entry can be regenerated for free.

**Different: a bigger model.** The sweep runs on the seat the table waits on; this runs
on `utility_batch`, and the difference is the point (Fable, 2026-08-14). Grounding catches
a name from nowhere, but it cannot catch a summary that has every fact right and their
relationship wrong — a live run had the 8B write that the party crossed a river they had
in fact been left on the wrong side of. Nothing about that sentence is ungrounded. The
only fix for a comprehension failure is comprehension, and minutes are free on a job
nobody is waiting for.

**Different: there is no confirmation gate.** The sweep's output enters the canon ledger,
which is the instrument this project measures drift with, so a human says yes first. A
chronicle entry is explicitly not canon — D-008 keeps it a separate family precisely so a
lossy summary cannot become fact — it is regenerable, and `chronicle.yaml` is hand-editable
data. It is printed at session end so a bad one is seen, and the prompt subordinates it to
the ledger. Asking the table to approve a paragraph of prose at the end of an evening buys
little and costs the thing that makes it usable, which is that it happens by itself.

Like the sweep, this never raises. A session must not end in a traceback because the GPU
box was asleep.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

from dndc.gm.chronicle import Chronicle, ChronicleEntry
from dndc.gm.context import Turn, render_transcript
from dndc.gm.templates import render_template
from dndc.logging import SessionLog
from dndc.memory.grounding import unknown_names, vocabulary
from dndc.memory.sweep import LOCAL_BILLING
from dndc.models import BATCH_SEAT
from dndc.models.base import GMBackend, GMBackendError, GMRequest, Message, Role
from dndc.schema.events import ChronicleWrite, Cost

#: Filename for a campaign's chronicle, alongside `canon.yaml`.
CHRONICLE_FILENAME = "chronicle.yaml"

#: A session's paragraph. Long enough to carry a session's shape, short enough that ten of
#: them are still cheaper than one transcript. Overruns are truncated at a sentence break
#: rather than rejected — an over-long summary is a verbose model, not a wrong one.
MAX_SUMMARY_CHARS = 1200

#: How many entries the chronicle carries before the oldest are folded into one, and how
#: many go into that fold. Eight sessions of individual detail is more than a returning GM
#: needs; past that, the early campaign is better as one paragraph than as four.
MAX_ENTRIES = 8
FOLD_OLDEST = 4

#: Slightly above the sweep's. Extraction wants the same answer twice; a summary has many
#: valid phrasings and greedy decoding on a small model produces a stilted one.
CHRONICLE_TEMPERATURE = 0.2

#: Rough tokens-per-character. Only used for `chronicle_write.token_estimate`, which exists
#: so the prompt budget can be watched without a tokenizer in the loop.
CHARS_PER_TOKEN = 4

_NO_PARTY = "(none named)"


@dataclass
class ChronicleReport:
    """What one end-of-session compression did, including having failed."""

    #: The session's own entry, if one was written.
    entry: ChronicleEntry | None = None
    #: The fold, if this run also compressed the older end of the chronicle.
    folded: ChronicleEntry | None = None
    calls: int = 0
    model: str | None = None
    #: Names the summary used that the session never did. Non-empty means it was rejected;
    #: worth surfacing, because it is a direct measurement of the utility seat.
    invented: list[str] = field(default_factory=list)
    #: True when the session was already in the chronicle — a second run is a no-op.
    already_covered: bool = False
    duration_ms: int = 0
    error: str | None = None

    @property
    def ran(self) -> bool:
        return self.error is None

    @property
    def wrote(self) -> bool:
        return self.entry is not None or self.folded is not None


class Chronicler:
    """Compresses a finished session into the campaign's chronicle."""

    def __init__(
        self,
        backend: GMBackend,
        chronicle: Chronicle | None = None,
        path: Path | str | None = None,
        log: SessionLog | None = None,
        max_tokens: int = 1024,
        billing: str = LOCAL_BILLING,
        party: Sequence[str] = (),
        max_entries: int = MAX_ENTRIES,
        fold_oldest: int = FOLD_OLDEST,
    ) -> None:
        self.backend = backend
        self.chronicle = chronicle if chronicle is not None else Chronicle()
        #: None means in-memory only, as with the canon store: a scratch session still
        #: logs its `chronicle_write`, it just has nowhere durable to keep it.
        self.path = Path(path) if path is not None else None
        self.log = log
        self.max_tokens = max_tokens
        self.billing = billing
        self.party = tuple(party)
        self.max_entries = max(1, max_entries)
        self.fold_oldest = max(2, fold_oldest)

    @classmethod
    def for_campaign(
        cls, backend: GMBackend, campaign_dir: Path | str, **kwargs
    ) -> Chronicler:
        path = Path(campaign_dir) / CHRONICLE_FILENAME
        return cls(backend, chronicle=Chronicle.load(path), path=path, **kwargs)

    # --- the job ------------------------------------------------------------

    def record(
        self,
        turns: Sequence[Turn],
        session: str | None = None,
        today: date | None = None,
    ) -> ChronicleReport:
        """Summarise a finished session, and fold the old end if it has grown too long."""
        report = ChronicleReport()
        playable = [turn for turn in turns if turn.narration.strip()]
        if not playable:
            return report
        if session and self.chronicle.covers(session):
            # Re-running the same session would file the evening twice and quietly double
            # its weight in every later prompt.
            report.already_covered = True
            return report

        started = time.monotonic()
        transcript = render_transcript(playable)
        summary = self._write(report, transcript, template="chronicle")
        if summary is not None:
            report.entry = self._file(summary, sessions=(session,) if session else (), today=today)
            self._fold(report, today=today)
        report.duration_ms = int((time.monotonic() - started) * 1000)
        return report

    def _fold(self, report: ChronicleReport, today: date | None = None) -> None:
        """Compress the oldest entries into one, once there are enough to be worth it.

        Without this the chronicle is a growing transcript in slow motion — which is the
        exact thing D-002's prompt rule exists to prevent, so leaving it for later would
        mean the layer works right up until the campaign is long enough to need it.
        """
        if len(self.chronicle) <= self.max_entries:
            return
        oldest = self.chronicle.entries[: self.fold_oldest]
        if len(oldest) < 2:
            return

        source = "\n\n".join(entry.summary for entry in oldest)
        summary = self._write(report, source, template="chronicle_fold")
        if summary is None:
            # A failed fold is not a failed session. The chronicle stays long, the entry
            # for tonight is already filed, and the next session tries again.
            return

        sessions = tuple(s for entry in oldest for s in entry.sessions)
        folded = ChronicleEntry(
            id=self.chronicle.mint_id(sessions or [oldest[0].id]),
            summary=summary,
            sessions=sessions,
            created=today or date.today(),
            model=report.model,
        )
        self.chronicle.replace([entry.id for entry in oldest], folded)
        self.save()
        self._emit(folded)
        report.folded = folded

    # --- one call -----------------------------------------------------------

    def _write(self, report: ChronicleReport, source: str, template: str) -> str | None:
        """One summary, checked against its source. One retry, then give up.

        The retry names the words that failed, which is the cheapest useful correction:
        the observed failure mode is a model importing a name from somewhere other than
        the text, and being shown the name is usually enough.
        """
        correction = ""
        for _ in range(2):
            response = self._call(report, source, template, correction)
            if response is None:
                return None
            summary = _tidy(response)
            if not summary:
                return None

            invented = unknown_names(summary, self._known(source))
            if not invented:
                report.invented = []
                return summary
            report.invented = invented
            correction = ", ".join(invented)
        return None

    def _call(
        self, report: ChronicleReport, source: str, template: str, correction: str
    ) -> str | None:
        request = GMRequest(
            system=render_template(
                template, party=self._party(), correction=_correction(correction)
            ),
            messages=(Message(role=Role.USER, content=source),),
            max_tokens=self.max_tokens,
            # Nothing to cache: one call per session, and the prefix differs every time.
            cache_system=False,
        )
        try:
            response = self.backend.generate(request)
        except GMBackendError as exc:
            report.error = str(exc)
            return None
        except Exception as exc:  # a local box that went away mid-call
            report.error = f"{type(exc).__name__}: {exc}"
            return None

        report.calls += 1
        report.model = response.model
        self._emit_cost(response)
        if response.refused or not response.text.strip():
            return None
        return response.text

    def _known(self, source: str) -> set[str]:
        """What the summary is allowed to name: whatever the source did, plus the party.

        The party is added explicitly because a character who did nothing this session
        may still belong in a sentence about the party, and their name would otherwise
        read as an invention.
        """
        known = vocabulary(source)
        for name in self.party:
            known |= vocabulary(name)
        return known

    def _party(self) -> str:
        if not self.party:
            return _NO_PARTY
        return "\n".join(f"- {name}" for name in self.party)

    # --- filing -------------------------------------------------------------

    def _file(
        self,
        summary: str,
        sessions: Sequence[str] = (),
        today: date | None = None,
    ) -> ChronicleEntry:
        entry = ChronicleEntry(
            id=self.chronicle.mint_id(sessions),
            summary=summary,
            sessions=tuple(sessions),
            created=today or date.today(),
            model=getattr(self.backend, "model", None),
        )
        self.chronicle.add(entry)
        self.save()
        self._emit(entry)
        return entry

    def save(self) -> Path | None:
        """Rewrite the chronicle file. No path configured is not an error."""
        if self.path is None:
            return None
        return self.chronicle.save(self.path)

    # --- logging ------------------------------------------------------------

    def _emit(self, entry: ChronicleEntry) -> ChronicleWrite | None:
        if self.log is None:
            return None
        return self.log.emit(
            ChronicleWrite,
            covers_sessions=entry.sessions,
            summary=entry.summary,
            model=entry.model,
            token_estimate=len(entry.summary) // CHARS_PER_TOKEN,
        )

    def _emit_cost(self, response) -> None:
        if self.log is None:
            return
        usage = response.usage
        self.log.emit(
            Cost,
            seat=BATCH_SEAT,
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd,
            call_id=response.call_id,
        )


def _correction(names: str) -> str:
    """The retry note, or nothing on the first attempt."""
    if not names:
        return ""
    return (
        "\n**Your previous attempt is rejected.** It used these names, which do not "
        f"appear anywhere in the transcript: {names}. Do not use them. Write only about "
        "what is actually in the text below.\n"
    )


def _tidy(text: str) -> str:
    """The summary as it will be stored: one block of prose, within budget.

    A small model asked for a paragraph sometimes writes four, and the tail is usually
    where it starts inventing. Truncation is at a sentence break so the stored text is
    never a half-sentence the GM has to finish for itself.
    """
    body = "\n".join(line.strip() for line in text.strip().splitlines())
    body = " ".join(body.split())
    if len(body) <= MAX_SUMMARY_CHARS:
        return body

    cut = body[:MAX_SUMMARY_CHARS]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: stop + 1].strip() if stop > 0 else cut.strip()
