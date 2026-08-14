"""Checking that a model's output came from the text it was reading.

Extracted from the P2.3 sweep, unchanged, because P2.5's chronicle needs the same guard
for the same reason. The reason is a live run: given a tightly-worded prompt with three
worked examples, `llama3.1:8b` answered with the three worked examples — including a
person and a place that appear nowhere in the transcript it had been handed. Prose cannot
stop that; it *was* prose that caused it.

So the claim is checked against its source, in code, and the check holds whatever model
ends up in the utility seat. Two tests:

* **Every name must appear in the source.** A capitalised word that is not
  sentence-initial is a name, and a name the session never mentioned is the signature of
  a model reciting rather than reading.
* **Half the substance must appear too.** Loose enough for honest paraphrase, which is
  what a good extraction is, and tight enough to catch a plausible invention.

The second test only makes sense for a single claim, so a summary — many sentences, whose
overlap with any one passage is naturally lower — uses `unknown_names` alone.
"""

from __future__ import annotations

import re

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

#: Words this short carry no evidence either way; requiring them to match would reject
#: honest paraphrase over "the" and "was".
MIN_CONTENT_LEN = 4

#: How much of a claim's substance has to appear in the text it was drawn from. Set by
#: what the first live run needed: a fact the model copied out of the prompt's own worked
#: examples scored near zero, and every genuine extraction scored well above this.
MIN_OVERLAP = 0.5


def stem(word: str) -> str:
    """A word as the grounding check compares it.

    Only the possessive is stripped, and only because "Ashmill's waystation" is what a
    paraphrase of "the waystation at Ashmill" actually looks like — the check rejected
    exactly that until this existed. Nothing further is stemmed: the point is to compare
    words, and a matcher clever enough to equate "burned" with "burning" is also clever
    enough to accept an invention.
    """
    folded = word.casefold().strip("-'’")
    for suffix in ("'s", "’s"):
        if folded.endswith(suffix):
            return folded[: -len(suffix)]
    return folded


def vocabulary(text: str) -> set[str]:
    """Every word in the source, as the check compares them."""
    return {stem(word) for word in WORD.findall(text)}


def unknown_names(statement: str, known: set[str]) -> list[str]:
    """Names in `statement` that the source never used, in the order they appear.

    A capitalised word not at the start of a sentence is treated as a name. That is a
    heuristic and it is meant to be: a model that invents an NPC almost always
    capitalises it, and the cost of a false positive is one rejected summary that can be
    regenerated for free.
    """
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", statement):
        for word in WORD.findall(sentence)[1:]:
            if word[0].isupper() and stem(word) not in known and word not in found:
                found.append(word)
    return found


def grounded(statement: str, known: set[str]) -> bool:
    """Does this single claim actually come from the text it claims to?"""
    words = WORD.findall(statement)
    if not words:
        return False
    if unknown_names(statement, known):
        return False

    content = [stem(word) for word in words if len(stem(word)) >= MIN_CONTENT_LEN]
    if not content:
        # Nothing long enough to check. The names passed, so let the table judge it.
        return True
    matched = sum(1 for word in content if word in known)
    return matched / len(content) >= MIN_OVERLAP
