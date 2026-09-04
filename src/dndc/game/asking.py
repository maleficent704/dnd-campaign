"""Questions the table has to answer before play goes on (P6.5).

Three things stop an evening and wait for a person: items the GM handed out (P2.4), facts
the sweep wants to file (P2.3), and where the recap thinks the party is standing (P5.3).
All three were blocking `rich` prompts, which is why a browser could take a turn but could
not finish a session.

**A question is data, not a prompt.** What it renders as is a front end's business; what it
*is* — a thing being asked, some options, and what silence means — is the same at a
terminal and on a phone. That split is why the same three confirmations can now be answered
from either.

**Silence is always no.** Every question here has a conservative reading and it is always
the same one: an item not applied, a fact not filed, a scene not changed. Nothing is lost
that cannot be redone, and each of the three already worked that way when stdin ran out —
this generalises it rather than inventing it. A browser closed mid-question must cost the
table a keystroke, never the evening.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: How long a served session waits for somebody to answer before taking silence for no.
#: Long enough that a phone can be picked up and read; short enough that an evening whose
#: only device went flat is not stuck until somebody notices.
ANSWER_TIMEOUT = 180.0

#: Kinds, so a device can render an item confirmation differently from a canon one without
#: the session knowing that it does.
INVENTORY = "inventory"
CANON = "canon"
SCENE = "scene"

#: What counts as taking the whole list, and what counts as taking none. Moved here from
#: the CLI unchanged: two callers had one retry policy between them and now three do.
SELECT_ALL = {"", "all", "a", "y", "yes", "*"}
SELECT_NONE = {"none", "n", "no", "nope", "0", "q", "skip"}


@dataclass(frozen=True)
class Choice:
    """One option, plus anything shown underneath it but not separately choosable.

    `detail` carries the sweep's near-duplicate alternates (Fable, 2026-08-14): grouped for
    display, one number per fact, and choosing the number declines the rest of its group.
    """

    text: str
    detail: tuple[str, ...] = ()


@dataclass(frozen=True)
class Question:
    """Something the table is being asked. Rendered by a front end, owned by the session."""

    kind: str
    prompt: str
    choices: tuple[Choice, ...] = ()
    #: Lines shown above the choices — the scene on file, a character with nobody to give
    #: an item to. Context, never options.
    notes: tuple[str, ...] = ()
    #: Set when a free-text reply is meaningful (the scene, which may be retyped rather
    #: than merely accepted or refused).
    accepts_text: bool = False

    def as_json(self) -> dict:
        return {
            "kind": self.kind,
            "prompt": self.prompt,
            "notes": list(self.notes),
            "accepts_text": self.accepts_text,
            "choices": [
                {"text": choice.text, "detail": list(choice.detail)} for choice in self.choices
            ],
        }


@dataclass(frozen=True)
class Answer:
    """What came back. `answered=False` is silence, and silence is no."""

    chosen: frozenset[int] = field(default_factory=frozenset)
    text: str = ""
    answered: bool = True

    @property
    def yes(self) -> bool:
        """For a yes/no question: was it accepted at all."""
        return self.answered and (bool(self.chosen) or bool(self.text))


#: What every question falls back to. Named, because "nobody answered" and "everybody said
#: no" must be distinguishable in a log even though they do the same thing.
SILENCE = Answer(answered=False)
NOTHING = Answer()


def parse_selection(answer: str, count: int) -> set[int] | None:
    """Which options the table kept. `None` means the answer made no sense.

    Returning `None` rather than an empty set matters: "" and "nonsense" must not both
    silently discard a session's worth of recovered canon. The caller asks again.

    Out-of-range numbers are dropped rather than rejecting the whole reply — somebody who
    types `1 3 9` at a list of four meant one and three.
    """
    cleaned = answer.strip().casefold()
    if cleaned in SELECT_ALL:
        return set(range(1, count + 1))
    if cleaned in SELECT_NONE:
        return set()

    numbers = {int(token) for token in re.findall(r"\d+", cleaned)}
    chosen = {number for number in numbers if 1 <= number <= count}
    return chosen or None


def read(question: Question, said: str) -> Answer | None:
    """One typed or posted reply, read against the question. None means unreadable.

    A scene question is the odd one: an empty reply accepts the proposal, `n` keeps the old
    scene, and anything else *is* the new scene — because the person answering is one of the
    two who were actually there, and making them retype a whole sentence into a yes/no box
    would be the interface arguing with them.
    """
    reply = said.strip()
    if question.kind == SCENE:
        if reply.casefold() in SELECT_NONE:
            return NOTHING
        if reply.casefold() in SELECT_ALL:
            return Answer(chosen=frozenset({1}))
        return Answer(chosen=frozenset({1}), text=reply)

    chosen = parse_selection(reply, len(question.choices))
    return None if chosen is None else Answer(chosen=frozenset(chosen))
