"""Canon ledger — **the P1.2 stub**, not the Phase 2 implementation.

D-002 makes the ledger the thing that makes "campaign" possible at all: typed facts with
provenance and scope, rebuilt into the prompt every turn instead of a growing transcript.
Phase 2 owns the parts with real machinery — the GM extraction pass that writes entries,
`canon_write` events, chronicle compression, the drift test.

What lives here is only what P1.2's context builder needs to consume: the entry type, the
scope enum, and a container that can be hand-authored, loaded, and rendered. It is
deliberately dumb — no extraction, no supersession, no compression. The shape is the
commitment; the machinery is Phase 2's.

Scopes exist because who-knows-what is structural, not a formatting concern. The GM sees
everything, including `gm_only`; the Phase 4 NPC tier will take filtered views of the
same entries (D-003), which is why the filtering lives on the ledger rather than in the
prompt builder.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field


class CanonScope(str, Enum):
    """Who a fact is true *for*."""

    #: Objectively true in the world, whether or not anyone knows it.
    WORLD = "world"
    #: Established in play — the players have seen or been told this.
    PLAYER_KNOWN = "player_known"
    #: True, and deliberately withheld: the twist, the villain, the trap.
    GM_ONLY = "gm_only"
    #: What a specific NPC believes, which may be false. Phase 4 reads these.
    NPC_BELIEF = "npc_belief"
    #: Player-character facts, mostly written at co-creation (D-005, P1.4).
    CHARACTER = "character"


class CanonEntry(BaseModel):
    """One established fact, with the provenance Phase 7 measures drift against."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    scope: CanonScope = CanonScope.WORLD
    #: Where this came from. `None` means authored rather than established in play.
    session: str | None = None
    turn: int | None = Field(default=None, ge=0)
    #: Required for NPC_BELIEF (whose belief?), optional elsewhere as a subject tag.
    subject: str | None = None
    tags: tuple[str, ...] = ()

    def render(self) -> str:
        """One prompt line. `gm_only` is marked, because the GM must not leak it."""
        prefix = "[GM ONLY] " if self.scope is CanonScope.GM_ONLY else ""
        if self.scope is CanonScope.NPC_BELIEF and self.subject:
            prefix = f"[{self.subject} believes] "
        return f"- {prefix}{self.text}"


class CanonLedger(BaseModel):
    """An ordered set of entries. Ordered because prompt stability matters for caching."""

    model_config = ConfigDict(extra="forbid")

    entries: list[CanonEntry] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[CanonEntry]:  # type: ignore[override]
        return iter(self.entries)

    def add(self, entry: CanonEntry) -> CanonEntry:
        """Append. A duplicate id is a bug, not something to silently overwrite."""
        if any(existing.id == entry.id for existing in self.entries):
            raise ValueError(f"canon entry id already used: {entry.id!r}")
        self.entries.append(entry)
        return entry

    def get(self, entry_id: str) -> CanonEntry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def scoped(self, scopes: Iterable[CanonScope]) -> list[CanonEntry]:
        wanted = set(scopes)
        return [entry for entry in self.entries if entry.scope in wanted]

    def for_gm(self) -> list[CanonEntry]:
        """Everything. The GM owns ground truth including the secrets (D-003)."""
        return list(self.entries)

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str) -> CanonLedger:
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


def render_entries(entries: Sequence[CanonEntry]) -> str:
    """Ledger lines for the prompt, grouped by scope so related facts sit together."""
    if not entries:
        return "(nothing established yet — this is the start of the campaign)"

    order = list(CanonScope)
    lines: list[str] = []
    for scope in order:
        in_scope = [entry for entry in entries if entry.scope is scope]
        if in_scope:
            lines.extend(entry.render() for entry in in_scope)
    return "\n".join(lines)
