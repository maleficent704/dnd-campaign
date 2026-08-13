"""The canon ledger's durable home during play (P2.1).

`CanonLedger` is a value: entries, scopes, supersession. This is the thing that owns one
on behalf of a running session — it writes the `canon_write` event, persists the file, and
enforces the contradiction rule at the one place every write passes through.

**Persisted on every write, not at session end.** A session that crashes at turn 40 must
not lose the world it spent forty turns building; the cost is rewriting a small YAML file
once per new fact, which is nothing beside the model call that produced it. The write is
atomic (temp file then replace) so a crash *during* the save cannot leave a half-written
ledger where a whole one used to be — losing the current fact is recoverable, losing the
campaign is not.

**The contradiction rule (ratified 2026-08-10).** Three things can happen when the GM
declares a fact:

* it is new — `establish()`, a `create` write;
* it restates something already in the ledger — suppressed, no entry and no event, because
  a ledger that grows by one row every time the GM mentions the town's name is not a
  ledger;
* it *contradicts* something in the ledger — `note_conflict()`. The existing entry is
  **kept** and the contradiction is logged against it.

That last one is the load-bearing decision. A ledger that quietly updates itself to match
the latest narration cannot measure drift, because it has agreed with the drift by
definition. Deliberate world change has its own path — `supersede()`, which keeps the old
entry on file with a pointer to its replacement. The difference between the two is
authorship: supersession is the GM saying the world changed, conflict is the GM
misremembering, and only the first is allowed to move ground truth.

**Every write says who wrote it** (`CanonSource`, D-008 amended 2026-08-12). Since P2.3
the ledger has two writers on two model tiers: the GM declaring facts inline as it
narrates, and the end-of-session sweep on a local 8B inferring what it forgot to declare.
They are not equally trustworthy, so the sweep's proposals are confirmed by the table
before they land and a declined one is logged via `decline()` without touching the ledger.

Scoping note: this makes the **world** survive a process restart, not the transcript.
Resuming a session mid-scene is Phase 5.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.canontag import CanonTag
from dndc.logging import SessionLog
from dndc.schema.events import CanonOperation, CanonSource, CanonWrite

#: Filename for a campaign's canon ledger, alongside `campaign.yaml`.
CANON_FILENAME = "canon.yaml"


def normalise(text: str) -> str:
    """Compare statements the way a reader would: case and spacing are not content."""
    return re.sub(r"\s+", " ", text).strip().casefold().rstrip(".")


class CanonStore:
    """A ledger, its file, and the log — the three things a canon write has to touch."""

    def __init__(
        self,
        ledger: CanonLedger | None = None,
        path: Path | str | None = None,
        log: SessionLog | None = None,
    ) -> None:
        self.ledger = ledger if ledger is not None else CanonLedger()
        #: None means in-memory only: a scratch session with `--character` and no campaign
        #: still logs its canon events, it just has nowhere durable to file them.
        self.path = Path(path) if path is not None else None
        self.log = log

    @classmethod
    def for_campaign(
        cls, campaign_dir: Path | str, log: SessionLog | None = None
    ) -> CanonStore:
        path = Path(campaign_dir) / CANON_FILENAME
        return cls(ledger=CanonLedger.load(path), path=path, log=log)

    # --- writes -------------------------------------------------------------

    def establish(
        self,
        text: str,
        scope: CanonScope = CanonScope.WORLD,
        subject: str | None = None,
        session: str | None = None,
        turn: int | None = None,
        established_by: str | None = None,
        source: CanonSource = CanonSource.GM_TAG,
    ) -> CanonEntry | None:
        """File a new fact. Returns None if the ledger already holds it.

        Restatement is the common case, not an error: the GM says "the waystation at
        Ashmill" every other turn. Suppressing it silently is right — there is no new
        information, so there is nothing for Phase 7 to measure.
        """
        if self.holds(text, scope):
            return None

        entry = CanonEntry(
            id=self.ledger.mint_id(scope, text),
            text=text.strip(),
            scope=scope,
            subject=subject,
            session=session,
            turn=turn,
        )
        self.ledger.add(entry)
        self._emit(entry, CanonOperation.CREATE, established_by=established_by, source=source)
        self.save()
        return entry

    def decline(
        self,
        text: str,
        scope: CanonScope = CanonScope.WORLD,
        established_by: str | None = None,
        source: CanonSource = CanonSource.SWEEP,
    ) -> CanonWrite | None:
        """A proposal the table refused. Logged, and the ledger is not touched.

        The same argument as `inventory_change.confirmed` (D-008): what a model proposed
        and the humans declined measures the proposer, and it is a measurement only if
        somebody writes it down. Precision of the P2.3 sweep is exactly this count against
        its accepted one.

        The id is minted but never reserved, so if the same fact is later established for
        real it lands on the same id — which is what makes the pair queryable rather than
        two unrelated rows.
        """
        entry = CanonEntry(id=self.ledger.mint_id(scope, text), text=text.strip(), scope=scope)
        return self._emit(
            entry,
            CanonOperation.CREATE,
            established_by=established_by,
            source=source,
            confirmed=False,
        )

    def supersede(
        self,
        entry_id: str,
        text: str,
        scope: CanonScope | None = None,
        subject: str | None = None,
        session: str | None = None,
        turn: int | None = None,
        established_by: str | None = None,
        source: CanonSource = CanonSource.AUTHORED,
    ) -> CanonEntry:
        """The world changed. The old entry stays on file, pointing at its replacement.

        Deliberate only. Nothing in the turn loop calls this on the GM's behalf — the GM
        contradicting itself is a conflict, not a world change, and Fable left the door
        open for a human retcon as an explicit table command rather than an automatic one.
        """
        existing = self.ledger.get(entry_id)
        if existing is None:
            raise KeyError(f"no canon entry {entry_id!r} to supersede")

        target_scope = scope if scope is not None else existing.scope
        replacement = CanonEntry(
            id=self.ledger.mint_id(target_scope, text),
            text=text.strip(),
            scope=target_scope,
            subject=subject if subject is not None else existing.subject,
            session=session,
            turn=turn,
        )
        self.ledger.supersede(entry_id, replacement)
        self._emit(
            replacement,
            CanonOperation.SUPERSEDE,
            established_by=established_by,
            supersedes=entry_id,
            source=source,
        )
        self.save()
        return replacement

    def note_conflict(self, entry_id: str, contradiction: str) -> CanonWrite | None:
        """Narration contradicted an entry. Log it; change nothing.

        `statement` carries the entry's surviving text — what canon still says — and
        `contradiction` goes into `established_by`, because what established *this row* is
        the narration that disagreed. Phase 7 needs both halves to say anything useful
        about how a campaign drifts; a conflict count alone says only that it did.
        """
        existing = self.ledger.get(entry_id)
        if existing is None:
            raise KeyError(f"no canon entry {entry_id!r} to conflict with")
        return self._emit(
            existing, CanonOperation.CONFLICT, established_by=contradiction
        )

    def record_tags(
        self,
        tags: Sequence[CanonTag],
        session: str | None = None,
        turn: int | None = None,
        source: CanonSource = CanonSource.GM_TAG,
    ) -> list[CanonEntry]:
        """Everything the GM declared this turn. Only the genuinely new comes back."""
        written = []
        for tag in tags:
            entry = self.establish(
                tag.text,
                scope=tag.scope,
                subject=tag.subject,
                session=session,
                turn=turn,
                established_by=tag.raw or None,
                source=source,
            )
            if entry is not None:
                written.append(entry)
        return written

    # --- reads --------------------------------------------------------------

    def holds(self, text: str, scope: CanonScope | None = None) -> bool:
        """Is this already established? Scope-aware: the same sentence as a world truth
        and as an NPC's belief are different facts, and one does not satisfy the other."""
        wanted = normalise(text)
        return any(
            normalise(entry.text) == wanted and (scope is None or entry.scope is scope)
            for entry in self.ledger.active()
        )

    # --- persistence --------------------------------------------------------

    def save(self) -> Path | None:
        """Atomically rewrite the ledger file. No path configured is not an error."""
        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(self.ledger.to_yaml(), encoding="utf-8")
        os.replace(temp, self.path)
        return self.path

    # --- logging ------------------------------------------------------------

    def _emit(
        self,
        entry: CanonEntry,
        operation: CanonOperation,
        established_by: str | None = None,
        supersedes: str | None = None,
        source: CanonSource = CanonSource.GM_TAG,
        confirmed: bool = True,
    ) -> CanonWrite | None:
        if self.log is None:
            return None
        return self.log.emit(
            CanonWrite,
            entry_id=entry.id,
            scope=entry.scope.value,
            operation=operation,
            statement=entry.text,
            established_by=established_by,
            supersedes=supersedes,
            source=source,
            confirmed=confirmed,
        )
