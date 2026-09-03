"""Parsing the GM's `[[BELIEF: ...]]` tag (P4.6) — a character changes their mind.

The ninth use of the `[[TAG:]]` convention, and the second one that costs a second model
call. It says something `[[CANON: npc_belief (...)]]` cannot: that what this character now
thinks **replaces** what they thought before.

    [[BELIEF: the caravan guard | the teamster is telling the truth]]

Why a second tag rather than a flag on the first. Learning something and changing your
mind are different events, and which one a sentence describes is not recoverable from the
sentence — "he now believes the crate never left the wagon" reads identically whether it
retires a belief or joins one. A character can perfectly well acquire a belief without
abandoning any: the guard hears the caravan master is back at the wagons, and still thinks
the teamster took the crate. Guessing wrong in one direction loses canon; in the other it
leaves a character holding two contradictory stories and saying whichever the sampler
reaches first. So the direction is **declared**, on the `[[GAIN/LOSE]]` precedent — a verb
that changes what happens to state is never a guessable field.

**What it does not decide is what gets retired.** The tag names the new belief and the
character; which of their standing beliefs it replaces is judged separately (`gm/stance.py`)
and can perfectly well be none. A tag is the GM's authorship of a change; the pass is the
bookkeeping the GM has no handle to do — the canon block in its prompt renders facts as
prose, without ids.

Forgiving on the format, strict on the cast, exactly as `[[SPEAK]]` is: pipe, arrow or
dash; a half with nothing in it is dropped rather than improvised; and matching the name
against the campaign's roster is the caller's business, not this module's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.gm.tagsyntax import split_directive, tidy

#: `[[BELIEF: the caravan guard | the teamster is telling the truth]]`. Non-greedy body,
#: so two changes of mind in one reply parse as two.
BELIEF_PATTERN = re.compile(
    r"\[\[\s*BELIEF\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class BeliefTag:
    """One declared change of mind. The name is as written — matching is the caller's."""

    name: str
    #: What they now believe. Never empty: a tag that names a character and says nothing
    #: about what changed is a formatting artifact, not a fact.
    belief: str
    raw: str = ""


def find_belief_tags(text: str) -> list[BeliefTag]:
    """Every change of mind in a GM reply, in the order it declared them.

    Unlike `[[SPEAK]]`, duplicates on the same name are **kept**. Two directions to one
    character in a turn would have her answer twice without hearing herself; two changes of
    mind are just two changes, applied in order, and collapsing them would silently drop
    the second half of "he stops believing X, and now thinks Y".
    """
    found: list[BeliefTag] = []
    for match in BELIEF_PATTERN.finditer(text):
        name, belief = split_directive(match.group("body"))
        if not name or not belief:
            # Half a tag establishes nothing. Dropping it is the same call `[[CANON]]`
            # makes on an empty body: a statement with no content is a slip in the
            # formatting, and inventing the missing half would be inventing canon.
            continue
        found.append(BeliefTag(name=name, belief=belief, raw=match.group(0)))
    return found


def strip_belief_tags(text: str) -> str:
    """The narration without the tags, for the screen and the recent window.

    Same reason as every other stripper: a tag left in the window comes back to the GM as
    its own past voice, and it learns to narrate in tags.
    """
    return tidy(BELIEF_PATTERN.sub("", text))


__all__ = [
    "BELIEF_PATTERN",
    "BeliefTag",
    "find_belief_tags",
    "strip_belief_tags",
]
