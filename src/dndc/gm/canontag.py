"""Parsing the GM's `[[CANON: ...]]` tag (P2.2) — how a fact gets into the ledger.

D-002 makes the canon ledger the thing that makes "campaign" possible, but something has
to *put facts in it*. Three mechanisms were on the table (PROGRESS.md 2026-08-09b): a
second model call per turn to extract facts (~2x per-turn cost), an end-of-session pass
only (the world is absent during the very session that established it), or the GM
declaring facts inline as it narrates. Inline won.

    [[CANON: <scope> (<subject>) — <the fact>]]

Scope and subject are optional; `[[CANON: The bridge at Aldermoor is out.]]` is a
well-formed world fact. This is the fourth use of the tag convention `[[CHECK]]`
established, and the `[[`-suppressing stream filter already keeps it off the players'
screens.

The parser's one hard rule: **it must never lose a fact to a formatting slip.** An
unrecognised leading word is treated as part of the statement rather than as a bad scope,
because a fact filed under the wrong scope is a smaller loss than a fact dropped on the
floor. That is the opposite of `[[CHECK]]`'s posture, and deliberately so — there, a
missing DC means the GM never set a difficulty and guessing one would invent the
adjudication the log exists to audit. Here, the fallback is simply the most common case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.gm.canon import CanonScope

#: The whole tag. Non-greedy body so two tags in one reply parse as two.
CANON_PATTERN = re.compile(r"\[\[\s*CANON\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)

#: Built from the enum rather than written out, so a new scope cannot be parseable in
#: one place and unknown in the other. `npc_belief` also matches `npc belief`/`npc-belief`.
_SCOPE_ALTERNATIVES = "|".join(
    sorted((scope.value.replace("_", "[ _-]?") for scope in CanonScope), key=len, reverse=True)
)

#: `<scope> (<subject>) <separator>` at the head of the body. The scope must match a real
#: scope word for this to fire at all — see the module docstring.
_HEAD = re.compile(
    rf"^\s*(?P<scope>{_SCOPE_ALTERNATIVES})\s*"
    rf"(?:\(\s*(?P<subject>[^)]+?)\s*\))?\s*"
    rf"(?:[—–]|--|[-:])\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CanonTag:
    """One fact the GM declared, ready for the ledger."""

    text: str
    scope: CanonScope = CanonScope.WORLD
    #: Whose belief, for `npc_belief`; an optional subject tag elsewhere.
    subject: str | None = None
    raw: str = ""


def find_canon_tags(text: str) -> list[CanonTag]:
    """Every canon declaration in a GM reply, in the order it made them."""
    tags = []
    for match in CANON_PATTERN.finditer(text):
        tag = _parse_body(match.group("body"), raw=match.group(0))
        if tag is not None:
            tags.append(tag)
    return tags


def strip_canon_tags(text: str) -> str:
    """The narration without the tags.

    The raw tag is machine instruction, not prose. Leaving it in would put a literal
    `[[CANON: ...]]` into the recent-turn window, where the GM reads it back as its own
    past voice and learns to narrate in tags.
    """
    return _tidy(CANON_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    """Close the hole the tag left behind.

    A tag lifted out of the middle of a sentence leaves two spaces where there was one,
    and that gap is on screen in front of the players. Only runs *after* a non-space
    character are collapsed, so a deliberately indented line keeps its indent.
    """
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_body(body: str, raw: str) -> CanonTag | None:
    """A tag with no statement left in it is not a fact; it is a formatting artifact."""
    head = _HEAD.match(body)
    if head is None:
        statement = body.strip()
        if not statement:
            return None
        return CanonTag(text=statement, scope=CanonScope.WORLD, raw=raw)

    statement = body[head.end():].strip()
    if not statement:
        return None
    return CanonTag(
        text=statement,
        scope=_scope(head.group("scope")),
        subject=(head.group("subject") or None),
        raw=raw,
    )


def _scope(word: str) -> CanonScope:
    return CanonScope(re.sub(r"[ -]", "_", word.strip().casefold()))
