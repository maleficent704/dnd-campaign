"""Parsing the GM's `[[TARGET: ...]]` tag (P3.7) — who the monster goes for.

Fable ruled on 2026-08-15 (c) that target selection belongs to the GM. It is *categorical*
judgment — "who does the goblin attack" needs no numbers — which puts it squarely on the
GM's side of D-001 under OD-12's own test. What kept it in the engine until now was
replayability, and that turned out to be solved already: a logged target choice is no
different from a logged DC. Replay reads the judgment back instead of re-asking.

    [[TARGET: <monster> -> <target>]]

The tag is a **declaration of intent for a turn that has not happened yet**, which is what
makes it free. The GM already gets one call per turn to narrate, and it has just been
shown the state, so it is better placed to say who the wolf goes for next than it would be
in a call of its own. Zero extra calls was a condition of the ruling.

Two consequences of declaring ahead, both handled rather than hidden:

* a declaration can be **overtaken by events** — the named target may be down by the time
  the turn arrives. The engine falls back and logs `stale`, because "the GM chose badly"
  and "the GM's choice expired" are different findings;
* a declaration can be **missing entirely**, which is not an error. The deterministic
  policy runs and is logged as `policy`. A fight must never stall on a missing tag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `[[TARGET: Wolf 1 -> Corin Vale]]`. The arrow may be `->`, `→`, or a dash, because the
#: producer is a language model and rejecting a turn over an en dash would be a bad trade.
TARGET_PATTERN = re.compile(
    r"\[\[\s*TARGET\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)

_ARROW = re.compile(r"\s*(?:->|-->|→|=>|[—–])\s*")


@dataclass(frozen=True)
class TargetDeclaration:
    """One monster's declared intent. Names as written; matching is the caller's."""

    actor: str
    target: str
    raw: str = ""


def find_target_declarations(text: str) -> list[TargetDeclaration]:
    """Every declaration in a GM reply, in the order it made them.

    A tag missing either name is dropped rather than half-read: a declaration that names
    an attacker and no victim tells the engine nothing it can act on, and guessing the
    victim is precisely the judgment the tag exists to hand over.
    """
    found = []
    for match in TARGET_PATTERN.finditer(text):
        parts = _ARROW.split(match.group("body").strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        actor, target = (part.strip() for part in parts)
        if not actor or not target:
            continue
        found.append(
            TargetDeclaration(actor=actor, target=target, raw=match.group(0))
        )
    return found


def strip_target_declarations(text: str) -> str:
    """The narration without the tags, for the screen and the recent window.

    Same reason as the other strippers: a tag left in the window comes back to the GM as
    its own past voice, and it learns to narrate in tags.
    """
    return _tidy(TARGET_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


__all__ = [
    "TARGET_PATTERN",
    "TargetDeclaration",
    "find_target_declarations",
    "strip_target_declarations",
]
