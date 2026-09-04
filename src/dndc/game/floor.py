"""Who has the floor, and the one queue every line arrives on (P6.4).

Two devices and a terminal can all try to speak. The question this module answers is not
"how do we merge them" but "how do we make sure only one of them is ever speaking" — and
the answer is the same one P6.1 gave for the loop: **there is one of it.**

**Every line runs on the play loop's thread, whatever typed it.** A browser submission
does not run a turn; it puts a line on this queue and returns, and the loop picks it up
exactly as it picks up a line from the keyboard. That is deliberate and it is the whole
safety argument: `PlaySession`, `TurnEngine`, the canon store and the save point are not
thread-safe and were never meant to be, so a second thread running a turn would be a race
against the campaign's own state — the kind that corrupts a ledger once a month and is
never reproducible.

**The terminal and the web are not treated identically, on purpose.** A line typed at the
keyboard is always accepted and queued: somebody in the room typed it, and telling them
"not now" would be answering for the table. A line from a browser is *refused* when it is
not that character's turn or when a turn is already running, because a device in another
room needs to be told, and silently queueing it would show a player their sentence
vanishing into an evening that had already moved on.

Nothing here requires a terminal. A hosted session with no keyboard attached (P6.7) is
the same object with one fewer source feeding it.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import Enum

#: Where a line came from. Kept on the line rather than inferred, because "who is actually
#: playing from where" is a thing the logs should be able to answer later.
TERMINAL = "terminal"
WEB = "web"


class Refusal(str, Enum):
    """Why a line was not accepted. Each maps to something a person can act on."""

    #: Somebody else has the floor.
    NOT_YOUR_TURN = "not_your_turn"
    #: The GM is still answering the last line.
    TURN_IN_FLIGHT = "turn_in_flight"
    #: A name that is not in this party.
    NO_SUCH_CHARACTER = "no_such_character"
    #: An empty submission.
    NOTHING_SAID = "nothing_said"


@dataclass(frozen=True)
class Line:
    """One thing somebody said, waiting to be played."""

    text: str
    source: str = TERMINAL
    #: Who said it. Empty from the terminal, where the loop already knows.
    character: str = ""


@dataclass(frozen=True)
class Offer:
    """The answer to "may I say this". `refusal` is None when the line was taken."""

    accepted: bool
    refusal: Refusal | None = None

    @property
    def reason(self) -> str:
        return "" if self.refusal is None else _REASONS[self.refusal]


_REASONS = {
    Refusal.NOT_YOUR_TURN: "it is not your turn",
    Refusal.TURN_IN_FLIGHT: "the GM is still answering the last line",
    Refusal.NO_SUCH_CHARACTER: "no such character in this party",
    Refusal.NOTHING_SAID: "say something first",
}

TAKEN = Offer(accepted=True)


class Floor:
    """The queue of things said, and the rule about who may add to it."""

    def __init__(self) -> None:
        self._lines: queue.Queue[Line] = queue.Queue()
        self._lock = threading.Lock()
        self._busy = False

    # --- speaking ----------------------------------------------------------

    def typed(self, text: str) -> None:
        """A line from the keyboard. Always taken — somebody in the room typed it."""
        self._lines.put(Line(text=text, source=TERMINAL))

    def offer(self, character: str, text: str, acting: str, party: set[str]) -> Offer:
        """A line from a device. Taken only if it is really this character's turn.

        `acting` and `party` are passed in rather than read off a session, because this
        object deliberately holds no campaign state — it decides about a line and owns a
        queue, and that is all it can do wrong.
        """
        said = text.strip()
        if not said:
            return Offer(False, Refusal.NOTHING_SAID)
        if character.casefold() not in {name.casefold() for name in party}:
            return Offer(False, Refusal.NO_SUCH_CHARACTER)
        if character.casefold() != acting.casefold():
            return Offer(False, Refusal.NOT_YOUR_TURN)
        with self._lock:
            if self._busy:
                return Offer(False, Refusal.TURN_IN_FLIGHT)
        self._lines.put(Line(text=said, source=WEB, character=character))
        return TAKEN

    # --- listening ---------------------------------------------------------

    def next(self, timeout: float | None = None) -> Line | None:
        """The next thing said, or None if nothing was said in time."""
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            return None

    # --- the turn ----------------------------------------------------------

    def taking_a_turn(self) -> "_Turn":
        """Marks a turn as in flight for as long as the block runs.

        A context manager rather than a pair of calls, because the one thing that must
        never happen is a turn that failed leaving the floor closed for the rest of the
        evening.
        """
        return _Turn(self)

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    @property
    def waiting(self) -> int:
        return self._lines.qsize()


class _Turn:
    def __init__(self, floor: Floor) -> None:
        self._floor = floor

    def __enter__(self) -> "_Turn":
        with self._floor._lock:
            self._floor._busy = True
        return self

    def __exit__(self, *exc) -> None:
        with self._floor._lock:
            self._floor._busy = False
