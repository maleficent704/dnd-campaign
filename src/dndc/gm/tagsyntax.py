"""The grammar shared by the `<name> | <body>` tags — `[[SPEAK]]` and `[[BELIEF]]`.

Two tags now name a character and then say something about them, and they have to agree
on what counts as a separator. Two copies of that regex is the "two drifting copies of one
rule" failure this repo has already had once (the grounding correction, 2026-08-14): the
copies do not diverge loudly, they diverge on one en dash at the table.

Forgiving on purpose. The producer is a language model and the cost of strictness is a
dropped instruction — an innkeeper who does not answer, or a change of mind that never
reaches the ledger — for the sake of punctuation nobody at the table can see.
"""

from __future__ import annotations

import re

#: Pipe first, because it is what the prompts ask for; the arrows and dashes are here
#: because rejecting an instruction over an en dash would be a bad trade.
SEPARATOR = re.compile(r"\s*(?:\||->|-->|→|=>|—|–)\s*")

#: Collapses "Maren:" and "Maren -" back to a name. Models punctuate a name they are
#: about to explain, and the punctuation is not part of who they meant.
TRAILING = re.compile(r"[\s:,;.\-]+$")


def split_directive(body: str) -> tuple[str, str]:
    """`"Maren | about the sheds"` -> `("Maren", "about the sheds")`.

    The second half may be absent; what an empty one *means* is the caller's business,
    because it differs — a bare `[[SPEAK]]` is "answer what was just said", while a bare
    `[[BELIEF]]` says nothing at all and is dropped.
    """
    parts = SEPARATOR.split(body.strip(), maxsplit=1)
    name = TRAILING.sub("", parts[0].strip())
    return name, (parts[1].strip() if len(parts) > 1 else "")


def tidy(text: str) -> str:
    """Close the hole a stripped tag left behind.

    A tag lifted out of the middle of a sentence leaves two spaces where there was one,
    and that gap is on screen in front of the players. Only runs *after* a non-space
    character are collapsed, so a deliberately indented line keeps its indent.
    """
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


__all__ = ["SEPARATOR", "TRAILING", "split_directive", "tidy"]
