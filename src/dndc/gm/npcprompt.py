"""Assembling an NPC's prompt (P4.2, D-003).

The half of the NPC tier that makes D-003's guarantee real. Everything here follows from
one rule, ported from the mystery:

**Substitution, never prohibition.** Every line of an assembled prompt says what this
character knows, believes, or does. There is no "do not mention the tunnel" anywhere,
because a prohibition names the secret in the same breath as forbidding it — the
pink-elephant anti-pattern. A secret is safe here because it was never assembled in.

Two construction choices carry that rule:

**The builder takes a ledger, never a list of entries.** There is deliberately no way to
hand it canon directly: it calls `CanonLedger.for_npc` itself, so the filter cannot be
forgotten, bypassed for convenience, or accidentally handed `ledger.active()` by a caller
in a hurry. The one door into an NPC prompt is the one with the lock on it.

**`NPC.notes` is never rendered.** That field exists for "she is lying about the ledger",
which is exactly the kind of thing the model voicing her must not be told. It is not
omitted by an oversight; it is omitted on purpose, tested, and should stay that way.

**Section order is data, not code.** `DEFAULT_SECTION_ORDER` is a hypothesis — identity
and knowledge first, demeanour and the claims ledger last, closest to the live exchange,
on the theory that recency governs behaviour. Order versus leak rate is a research
variable Phase 7 can move, so the builder takes an override rather than hard-coding the
sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.templates import render_template
from dndc.models.base import DEFAULT_MAX_TOKENS, GMRequest, Message, Role
from dndc.schema.npc import NPC

#: Identity sections, in the order they are rendered into the cached system prefix.
#: A hypothesis about what governs voice, not a rule — see the module docstring.
DEFAULT_SECTION_ORDER: tuple[str, ...] = (
    "role",
    "persona",
    "manner",
    "samples",
    "demeanour",
)

_NOTHING_KNOWN = (
    "(you have heard nothing worth repeating — you know your own business and no more)"
)


class NPCPromptError(RuntimeError):
    """The prompt could not be assembled as asked."""


@dataclass(frozen=True)
class NPCScene:
    """What is true *now*, as opposed to what this character is.

    Turn-scoped, so it rides outside the cached prefix. `said` is the claims ledger: what
    this NPC has already told these people. It is here from P4.2 because consistency
    across a conversation is most of what an NPC tier is for — an innkeeper who
    contradicts her own last answer is the failure the mystery's ledger was built to end.
    """

    #: Where this is happening, in a line. The GM's words, not the NPC's.
    setting: str = ""
    #: What this character has already said to these people, oldest first.
    said: Sequence[str] = ()
    #: What the party just said or did, as the GM describes it to this character.
    prompt: str = ""


class NPCPromptBuilder:
    """Builds one call for one NPC. Holds no conversation — the caller owns that."""

    def __init__(self, order: Sequence[str] = DEFAULT_SECTION_ORDER) -> None:
        unknown = [name for name in order if name not in _SECTIONS]
        if unknown:
            raise NPCPromptError(
                f"unknown prompt section(s): {', '.join(unknown)} "
                f"(have: {', '.join(sorted(_SECTIONS))})"
            )
        self.order = tuple(order)

    # --- the halves --------------------------------------------------------

    def system(self, npc: NPC, ledger: CanonLedger) -> str:
        """Conduct, identity, and everything this character knows.

        The knowledge lives in the cached half rather than the volatile one because it is
        *stable for the scene* — canon changes between scenes, not between sentences — and
        because an NPC's knowledge is the largest part of its prompt. Splitting it out
        would put the cache breakpoint before the only part big enough to be worth caching.
        """
        return render_template(
            "npc_core",
            name=npc.name,
            identity=self._identity(npc),
            knowledge=self._knowledge(npc, ledger),
        )

    def volatile(self, scene: NPCScene) -> str:
        """The scene and the claims ledger — what changed since the last call."""
        blocks: list[str] = []
        if scene.setting:
            blocks.append(f"## Where you are\n\n{scene.setting}")
        if scene.said:
            blocks.append(
                "## What you have already told them\n\n"
                + "\n".join(f"- {line}" for line in scene.said)
                + "\n\nStay consistent with it, unless something has genuinely changed "
                "your mind — and if it has, say so plainly rather than pretending you "
                "never said the first thing."
            )
        return "\n\n".join(blocks)

    def build(
        self,
        npc: NPC,
        ledger: CanonLedger,
        scene: NPCScene,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        call_id: str | None = None,
    ) -> GMRequest:
        """One NPC call. `ledger` is filtered here — callers cannot pass entries."""
        return GMRequest(
            system=self.system(npc, ledger),
            system_volatile=self.volatile(scene),
            messages=(Message(role=Role.USER, content=scene.prompt),) if scene.prompt else (),
            model=model,
            max_tokens=max_tokens,
            call_id=call_id,
        )

    # --- sections ----------------------------------------------------------

    def _identity(self, npc: NPC) -> str:
        rendered = [text for name in self.order if (text := _SECTIONS[name](npc))]
        return "\n\n".join(rendered)

    def _knowledge(self, npc: NPC, ledger: CanonLedger) -> str:
        """Everything this character may be told, split into fact and belief.

        Split because the two are not the same kind of thing and a model that treats them
        alike will assert a belief as established fact — which is how an NPC's private
        suspicion becomes, three turns later, something "everyone knows".
        """
        permitted = ledger.for_npc(npc)
        beliefs = [e for e in permitted if e.scope is CanonScope.NPC_BELIEF]
        facts = [e for e in permitted if e.scope is not CanonScope.NPC_BELIEF]

        blocks: list[str] = []
        if facts:
            blocks.append(_bullets(facts))
        if beliefs:
            blocks.append(
                "What you believe, rightly or wrongly — this is your own view and not "
                "something you have been shown:\n" + _bullets(beliefs)
            )
        return "\n\n".join(blocks) if blocks else _NOTHING_KNOWN


def _bullets(entries: Sequence[CanonEntry]) -> str:
    """Plain lines. Deliberately **not** `CanonEntry.render`, whose prefixes are written
    for the GM's view — "[Maren believes]" addressed to Maren is the machine showing
    through, and "[GM ONLY]" must never be renderable here at all."""
    return "\n".join(f"- {entry.text}" for entry in entries)


def _role(npc: NPC) -> str:
    parts = [part for part in (npc.voice.role, npc.pronouns) if part]
    return f"You are {'; '.join(parts)}." if parts else ""


#: Each section renders itself or renders nothing. A section with no content produces an
#: empty string rather than an empty heading, so a thin voice card reads as a thin
#: character rather than as a form somebody failed to fill in.
_SECTIONS: dict[str, Callable[[NPC], str]] = {
    "role": _role,
    "persona": lambda npc: npc.voice.persona,
    "manner": lambda npc: f"How you talk: {npc.voice.manner}" if npc.voice.manner else "",
    "samples": lambda npc: (
        "Things you have been heard to say:\n"
        + "\n".join(f'- "{line}"' for line in npc.voice.sample_lines)
        if npc.voice.sample_lines
        else ""
    ),
    "demeanour": lambda npc: (
        f"Your manner with these people right now: {npc.voice.demeanour}"
        if npc.voice.demeanour
        else ""
    ),
}
