"""Parsing the GM's `[[SPEAK: ...]]` tag (P4.5) — who answers, in their own voice.

The eighth use of the `[[TAG:]]` convention and the first one that costs a second model
call. Everything else the GM declares is an instruction to the engine; this is an
instruction to *another character*.

    [[SPEAK: Maren | they have asked her outright about the salt sheds]]
    [[SPEAK: Maren]]

**The direction is a stage direction, not a script.** It says what the character is being
asked, never what they should reply. That distinction is the whole point of routing the
line through a second model at all: the GM holds `gm_only` canon and Maren does not, so a
GM that could dictate her words would have routed around D-003 entirely. Nothing here can
enforce it — the tag is prose — so the rule lives in the GM prompt and the direction is
logged verbatim (`npc_turn.direction`), where a Phase 7 reader can check whether it was
kept.

**Forgiving on the format, strict on the cast.** The separator may be a pipe or an arrow,
and the direction may be missing entirely — a bare tag means "answer what was just said".
But a name with no record in `npcs.yaml` is *dropped*, not improvised: the tier exists for
characters whose knowledge is worth scoping, and voicing a passer-by is something the GM
has always done in its own prose. Resolution against the cast is the caller's, not this
module's; parsing does not get to know what a campaign contains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `[[SPEAK: Maren | about the sheds]]`. Same shape as the other tags, same tolerance for
#: whatever spacing and casing a language model feels like producing.
SPEAK_PATTERN = re.compile(r"\[\[\s*SPEAK\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)

#: Pipe first, because it is what the prompt asks for; the arrows are here for the same
#: reason `TARGET` accepts them — rejecting a turn over an en dash would be a bad trade.
_SEPARATOR = re.compile(r"\s*(?:\||->|-->|→|=>|—|–)\s*")

#: Collapses "Maren:" and "Maren -" back to a name. Models punctuate a name they are
#: about to explain, and the punctuation is not part of who they meant.
_TRAILING = re.compile(r"[\s:,;.\-]+$")


@dataclass(frozen=True)
class SpeakDirection:
    """One character, directed. The name is as written — matching is the caller's."""

    name: str
    #: What the GM asked them to address. Empty means "answer what was just said", which
    #: the engine fills from the player's own words rather than inventing a prompt.
    direction: str = ""
    raw: str = ""


def find_speak_directions(text: str) -> list[SpeakDirection]:
    """Every direction in a GM reply, in the order it made them.

    Duplicates are collapsed on the name, keeping the first: a GM that names the same
    character twice in one reply has repeated itself, and running two calls for one
    character would have her answer, then answer again without having heard herself.
    """
    found: list[SpeakDirection] = []
    seen: set[str] = set()
    for match in SPEAK_PATTERN.finditer(text):
        parts = _SEPARATOR.split(match.group("body").strip(), maxsplit=1)
        name = _TRAILING.sub("", parts[0].strip())
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        direction = parts[1].strip() if len(parts) > 1 else ""
        found.append(
            SpeakDirection(name=name, direction=direction, raw=match.group(0))
        )
    return found


def strip_speak_directions(text: str) -> str:
    """The narration without the tags, for the screen and the recent window.

    Same reason as every other stripper: a tag left in the window comes back to the GM as
    its own past voice, and it learns to narrate in tags. It matters more here than
    anywhere — a GM reading its own `[[SPEAK:]]` beside the line that followed it is one
    short step from writing both halves itself.
    """
    return _tidy(SPEAK_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


__all__ = [
    "SPEAK_PATTERN",
    "SpeakDirection",
    "find_speak_directions",
    "strip_speak_directions",
]
