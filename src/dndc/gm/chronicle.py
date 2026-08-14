"""Campaign chronicle — D-002's third memory layer.

Three layers: the session log is everything that happened, the canon ledger is the
discrete facts, and this is the shape of the story in between. A ledger can tell the GM
that the mill burned down and that Halda keeps the waystation; it cannot tell it that the
party spent an evening failing to get a straight answer out of her, which is the sort of
thing a returning GM needs in order to sound like it was there.

Deliberately **not** canon, and D-008 keeps `chronicle_write` a separate event family for
the same reason: a chronicle entry is lossy prose about many turns, where a canon entry is
a discrete fact with provenance. Conflating them would let a compression artifact enter the
ledger as an established fact. Where the two disagree, the ledger wins — the prompt says
so, in the same terms as the ratified contradiction rule.

One entry per session, until there are enough of them to matter; then the oldest fold into
one entry covering several sessions (`sessions` is a tuple for exactly that reason). That
fold is what keeps D-002's promise: the prompt is rebuilt from ledger + chronicle + window
and must stay bounded, and a chronicle that grows one paragraph per session forever is a
growing transcript wearing a hat.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Iterator, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field

_NOTHING = "(nothing yet — this is the first session)"


class ChronicleEntry(BaseModel):
    """One compressed stretch of campaign, as prose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    #: The session ids this covers, oldest first. More than one means it is a fold.
    sessions: tuple[str, ...] = ()
    #: When it was written, not when the sessions happened.
    created: date | None = None
    #: Which model compressed it — the utility seat, and worth recording for the same
    #: reason `canon_write.source` exists: these are not all written by the same thing.
    model: str | None = None

    @property
    def folded(self) -> bool:
        return len(self.sessions) > 1

    def render(self) -> str:
        return self.summary.strip()


class Chronicle(BaseModel):
    """The campaign's summaries, oldest first. Order is the story's order."""

    model_config = ConfigDict(extra="forbid")

    entries: list[ChronicleEntry] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[ChronicleEntry]:  # type: ignore[override]
        return iter(self.entries)

    def add(self, entry: ChronicleEntry) -> ChronicleEntry:
        if any(existing.id == entry.id for existing in self.entries):
            raise ValueError(f"chronicle entry id already used: {entry.id!r}")
        self.entries.append(entry)
        return entry

    def get(self, entry_id: str) -> ChronicleEntry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def covers(self, session_id: str) -> bool:
        """Is this session already summarised? Guards against a double run."""
        return any(session_id in entry.sessions for entry in self.entries)

    def sessions(self) -> tuple[str, ...]:
        return tuple(s for entry in self.entries for s in entry.sessions)

    def replace(self, entry_ids: Sequence[str], folded: ChronicleEntry) -> ChronicleEntry:
        """Swap a run of entries for the one that now covers them.

        The originals are *dropped*, not kept the way superseded canon is. That asymmetry
        is deliberate: superseded canon is the record of what used to be true, which is
        what drift is measured against, whereas a pre-fold summary is just a longer
        version of the text replacing it. The session log still holds every word.
        """
        wanted = list(entry_ids)
        if not wanted:
            raise ValueError("no chronicle entries named to fold")
        indices = [i for i, entry in enumerate(self.entries) if entry.id in wanted]
        if len(indices) != len(wanted):
            missing = set(wanted) - {self.entries[i].id for i in indices}
            raise KeyError(f"no chronicle entries to fold: {sorted(missing)}")

        at = indices[0]
        for index in reversed(indices):
            del self.entries[index]
        self.entries.insert(at, folded)
        return folded

    def mint_id(self, sessions: Sequence[str]) -> str:
        """A readable, stable id. These are read by humans in `chronicle.yaml`."""
        clean = [re.sub(r"[^A-Za-z0-9]+", "", s) for s in sessions if s]
        if not clean:
            base = "session"
        elif len(clean) == 1:
            base = clean[0]
        else:
            base = f"{clean[0]}-{clean[-1]}"
        taken = {entry.id for entry in self.entries}
        if base not in taken:
            return base
        index = 2
        while f"{base}-{index}" in taken:
            index += 1
        return f"{base}-{index}"

    def render(self) -> str:
        """The chronicle as the GM reads it: oldest first, one paragraph each."""
        if not self.entries:
            return _NOTHING
        return "\n\n".join(entry.render() for entry in self.entries)

    def characters(self) -> int:
        """How much prompt this costs, in the only unit available without a tokenizer."""
        return sum(len(entry.summary) for entry in self.entries)

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str) -> Chronicle:
        target = Path(path)
        if not target.exists():
            return cls()
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target

    def to_yaml(self) -> str:
        payload = self.model_dump(mode="json", exclude_defaults=True)
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
