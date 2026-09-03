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

import re
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dndc.schema.npc import COMMON_KNOWLEDGE_TAG, NPC


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


#: Scopes no NPC call may ever carry, whatever `npcs.yaml` says (P4.1, D-003). A frozen
#: set rather than a chain of `if`s because this list is the guarantee: anything added
#: here becomes unreachable by every NPC in every campaign, in one edit.
_NEVER_FOR_NPCS = frozenset({CanonScope.GM_ONLY, CanonScope.PLAYER_KNOWN})


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
    #: Id of the entry that replaced this one. Superseded entries stay in the ledger —
    #: they are the record of what was true before, which is what drift is measured
    #: against — but they leave the prompt.
    superseded_by: str | None = None

    @property
    def active(self) -> bool:
        return self.superseded_by is None

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
        return [entry for entry in self.active() if entry.scope in wanted]

    def active(self) -> list[CanonEntry]:
        """Entries still standing. Superseded ones stay on file but leave the prompt."""
        return [entry for entry in self.entries if entry.active]

    def for_gm(self) -> list[CanonEntry]:
        """Everything still true. The GM owns ground truth, secrets included (D-003)."""
        return self.active()

    def for_npc(self, npc: NPC) -> list[CanonEntry]:
        """What one NPC may be told — the structural half of D-003 (P4.1).

        An allow-list, not a deny-list. A fact reaches this character because they were
        given it (tagged, named outright, or common knowledge in this campaign) or because
        it is their own belief. Everything else is simply absent from the call, which is
        what makes a secret safe from a model that cannot be trusted to keep one.

        Three exclusions are **unconditional**, and none can be overridden by authoring —
        not by a tag, not by naming the entry in `knows`. That absoluteness is the point:
        it makes "no NPC prompt has ever carried this" a property of the code rather than
        of whoever last edited `npcs.yaml`.

        - **`gm_only`.** The twist, the villain, the trap. If a character genuinely knows
          a secret, that is a *belief* of theirs and belongs in an `npc_belief` entry with
          their name on it — which this view does return.
        - **`player_known`.** The least obvious and the most load-bearing. What the party
          has established is not what this innkeeper has heard, and the exclusion has to be
          unconditional rather than merely default because **the end-of-session sweep writes
          this scope automatically** (P2.3 forces it in code). So it is the one bucket that
          fills up with everything the party did and learned without anyone authoring it,
          and letting a coarse tag reach into it would open a leak that grows by itself.
          A thing the world also knows is a `world` fact, or that character's belief.
        - **Another character's beliefs.** `npc_belief` entries belong to their subject
          alone. A village where everyone can see what everyone else privately thinks has
          no secrets left in it.
        """
        tags = {tag.casefold() for tag in npc.knows_tags}
        if npc.common_knowledge:
            tags.add(COMMON_KNOWLEDGE_TAG)
        named = {entry_id.strip() for entry_id in npc.knows}
        subject = npc.name.casefold()

        visible: list[CanonEntry] = []
        for entry in self.active():
            if entry.scope in _NEVER_FOR_NPCS:
                continue
            if entry.scope is CanonScope.NPC_BELIEF:
                if entry.subject and entry.subject.casefold() == subject:
                    visible.append(entry)
                continue
            if entry.id in named or tags & {tag.casefold() for tag in entry.tags}:
                visible.append(entry)
        return visible

    def mint_id(self, scope: CanonScope, hint: str) -> str:
        """A stable, readable id that does not collide with one already in the ledger.

        Readable because these are read by humans in `canon.yaml` and in drift reports;
        derived from the text so the same fact tends to land on the same id across runs,
        which makes a replay diff mean something.
        """
        stem = re.sub(r"[^a-z0-9]+", "-", hint.casefold()).strip("-")
        stem = "-".join(stem.split("-")[:4]) or "entry"
        base = f"{scope.value}-{stem}"
        taken = {entry.id for entry in self.entries}
        if base not in taken:
            return base
        index = 2
        while f"{base}-{index}" in taken:
            index += 1
        return f"{base}-{index}"

    def supersede(self, entry_id: str, replacement: CanonEntry) -> CanonEntry:
        """Replace an entry, keeping the old one on file as history.

        This is the *deliberate* path — the GM establishing that something has changed in
        the world. It is not what happens when narration merely contradicts the ledger;
        that is a conflict, the entry is kept, and nothing here is called (D-008's
        `conflict` operation). Keeping the two distinct is the whole point: a campaign
        where the ledger silently follows the latest narration cannot measure drift,
        because it has agreed with the drift by definition.
        """
        existing = self.get(entry_id)
        if existing is None:
            raise KeyError(f"no canon entry {entry_id!r} to supersede")
        if not existing.active:
            raise ValueError(
                f"canon entry {entry_id!r} was already superseded by "
                f"{existing.superseded_by!r}"
            )
        self.add(replacement)
        self.entries[self.entries.index(existing)] = existing.model_copy(
            update={"superseded_by": replacement.id}
        )
        return replacement

    def retire(self, entry_id: str, replacement_id: str) -> CanonEntry:
        """Point an entry at a replacement that is **already** in the ledger (P4.6).

        `supersede` files a new fact and retires one, which is the right shape when the
        world changes once. A change of mind is the other shape: one new belief can retire
        several older ones, and minting a fresh copy of the same sentence per retirement
        would put three identical beliefs in the ledger and leave Phase 7 counting them as
        three separate things this character came to think.
        """
        existing = self.get(entry_id)
        if existing is None:
            raise KeyError(f"no canon entry {entry_id!r} to retire")
        if not existing.active:
            raise ValueError(
                f"canon entry {entry_id!r} was already superseded by "
                f"{existing.superseded_by!r}"
            )
        replacement = self.get(replacement_id)
        if replacement is None:
            raise KeyError(f"no canon entry {replacement_id!r} to retire {entry_id!r} in favour of")
        if replacement.id == entry_id:
            raise ValueError(f"canon entry {entry_id!r} cannot supersede itself")
        self.entries[self.entries.index(existing)] = existing.model_copy(
            update={"superseded_by": replacement.id}
        )
        return replacement

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


def npc_issues(npc: NPC, ledger: CanonLedger) -> list[str]:
    """Ways an NPC's knowledge scope does not say what its author meant (P4.1).

    Reports rather than raises, like `grant_issues`: `npcs.yaml` is hand-edited data, and
    the caller is inspecting a file rather than constructing something. The failures worth
    catching are all silent ones — a scope that quietly grants nothing produces a character
    with nothing to say, and nothing anywhere complains.
    """
    issues: list[str] = []
    for entry_id in npc.knows:
        entry = ledger.get(entry_id)
        if entry is None:
            issues.append(f"knows {entry_id!r}, which is not in the ledger")
            continue
        if entry.scope in _NEVER_FOR_NPCS:
            issues.append(
                f"knows {entry_id!r}, which is {entry.scope.value} and will never be shown "
                f"to an NPC. If {npc.name} genuinely knows it, record it as world canon or "
                f"as their belief (scope npc_belief, subject {npc.name})."
            )
        elif entry.scope is CanonScope.NPC_BELIEF and (
            not entry.subject or entry.subject.casefold() != npc.name.casefold()
        ):
            whose = entry.subject or "another character"
            issues.append(
                f"knows {entry_id!r}, which is {whose}'s belief — beliefs reach their "
                f"subject only"
            )
        elif not entry.active:
            issues.append(f"knows {entry_id!r}, which has been superseded")

    tagged = {tag.casefold() for entry in ledger.active() for tag in entry.tags}
    for tag in npc.knows_tags:
        if tag.casefold() not in tagged:
            issues.append(f"knows tag {tag!r}, which no canon entry carries")

    if not ledger.for_npc(npc):
        issues.append(
            "knows nothing at all — this character has no canon to speak from, and will "
            "have nothing to say beyond their voice card"
        )
    return issues


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
