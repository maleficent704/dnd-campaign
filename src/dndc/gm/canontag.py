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

#: The whole tag. Non-greedy body so two tags in one reply parse as two. `LEARNED` is the
#: same grammar with the discovery axis set (D-008 item 31) — one pattern rather than two
#: so a reply cannot have a fact read by one parser and missed by the other.
CANON_PATTERN = re.compile(
    r"\[\[\s*(?P<verb>CANON|LEARNED)\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)

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
    #: Written as `[[LEARNED: ...]]` — the party has found this out (D-008 item 31). The
    #: store turns it into a new discovered fact or, when the ledger already holds the
    #: statement, into a reveal.
    discovered: bool = False


def find_canon_tags(text: str) -> list[CanonTag]:
    """Every canon declaration in a GM reply, in the order it made them."""
    tags = []
    for match in CANON_PATTERN.finditer(text):
        tag = _parse_body(
            match.group("body"),
            raw=match.group(0),
            discovered=match.group("verb").casefold() == "learned",
        )
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


def _parse_body(body: str, raw: str, discovered: bool = False) -> CanonTag | None:
    """A tag with no statement left in it is not a fact; it is a formatting artifact.

    A `[[LEARNED:]]` is always a world fact whatever scope word it carries. The other
    scopes are not things a party can be told: `gm_only` discovered is a contradiction in
    terms, `npc_belief` is one character's private mind, and `character` facts are the
    player's own and known by construction. So the scope head is read and then overruled,
    rather than the tag being refused — this parser's one hard rule is that it never loses
    a fact to a formatting slip, and a GM writing `[[LEARNED: world — ...]]` has done
    nothing wrong.
    """
    head = _HEAD.match(body)
    if head is None:
        statement = body.strip()
        if not statement:
            return None
        return CanonTag(
            text=statement, scope=CanonScope.WORLD, raw=raw, discovered=discovered
        )

    statement = body[head.end():].strip()
    if not statement:
        return None
    scope = _scope(head.group("scope"))
    if scope is CanonScope.PLAYER_KNOWN:
        # The retired scope (D-008 item 30) means exactly what `[[LEARNED:]]` means, so a
        # GM that writes it gets what it asked for. Normalised here rather than at the
        # ledger so everything downstream — id minting, the restatement check, the event —
        # sees one shape. It stays parseable because the GM prompt said this word for two
        # phases and a model that read an old transcript will use it again.
        scope, discovered = CanonScope.WORLD, True
    return CanonTag(
        text=statement,
        scope=CanonScope.WORLD if discovered else scope,
        subject=None if discovered else (head.group("subject") or None),
        raw=raw,
        discovered=discovered,
    )


def _scope(word: str) -> CanonScope:
    return CanonScope(re.sub(r"[ -]", "_", word.strip().casefold()))
