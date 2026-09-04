"""What a watching device is shown, and how it finds out (P6.3).

The mirror is read-only in the strong sense: it holds no campaign state, owns no engine,
and has no method that changes anything. It is handed a `TableView` when one is built and
a chunk of text when the GM is mid-sentence, and it hands those on to whoever is watching.
An instrument that alters what it measures is not an instrument (P2.6's doctrine, and the
same argument applies to a screen).

**Streamed text goes through `TagStream` here, not somewhere else.** That is the only
reason this class touches text at all. `web/view.py` guarantees a `gm_only` fact cannot
reach a device because its types have nowhere to put one — but live narration arrives raw,
straight off the model, with `[[CANON: gm_only — ...]]` in it, and it does not pass through
those types at all. Filtering it *at the point it enters the mirror* is what keeps the
guarantee true for the whole surface rather than most of it.

Subscribers are plain queues. A device that stops reading fills its own queue and is
dropped; it must not be able to hold up a turn, because the evening belongs to the people
in the room and not to a phone somebody left on the sofa.
"""

from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass, field

from dndc.gm.tagstream import TagStream
from dndc.web.view import TableView

#: How many undelivered messages a watching device may fall behind by before it is cut
#: loose. Generous enough to cover a phone waking up, small enough that a dead socket
#: cannot grow without bound.
BACKLOG = 256

#: The last message any watcher receives. A stream that has sent it is finished, which is
#: what lets a connection close cleanly instead of being dropped by a timeout.
ENDED = {"kind": "ended"}

#: Sent when nothing has happened for a while, so a proxy or a sleeping phone does not
#: quietly close a connection everyone believes is open.
KEEPALIVE = "ping"


@dataclass
class Watcher:
    """One connected device."""

    queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=BACKLOG))

    def send(self, message: str) -> bool:
        """Queue a message. False means this device has fallen too far behind."""
        try:
            self.queue.put_nowait(message)
            return True
        except queue.Full:
            return False


class Mirror:
    """The live state of one session, and everyone watching it.

    Thread-safe because the session runs on the CLI's thread and the server answers on
    its own. Every method here is called from the play loop except `subscribe`/`snapshot`,
    which are called from the server.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watchers: list[Watcher] = []
        self._table: TableView | None = None
        #: Text of the reply currently being written, tags already removed. Cleared when
        #: the turn settles into the transcript, so it is never shown twice.
        self._pending = ""
        self._tags = TagStream()
        #: Lines spoken since the last settled state, for a device that connects mid-turn.
        self._spoken: list[dict] = []
        self._ended = False

    # --- what the play loop tells it ---------------------------------------

    def show(self, table: TableView) -> None:
        """A turn has settled. This is the truth; anything pending was a preview of it."""
        with self._lock:
            self._table = table
            self._pending = ""
            self._tags = TagStream()
            self._spoken = []
            self._push({"kind": "table", "table": table.model_dump(mode="json")})

    def narrate(self, chunk: str) -> None:
        """A piece of the GM's reply, straight off the model and not yet safe to show."""
        text = self._tags.feed(chunk)
        if not text:
            return
        with self._lock:
            self._pending += text
            self._push({"kind": "narrating", "text": text})

    def settle(self) -> None:
        """The reply is over. Releases anything the tag filter was still holding."""
        text = self._tags.finish()
        if not text:
            return
        with self._lock:
            self._pending += text
            self._push({"kind": "narrating", "text": text})

    def spoke(self, speaker: str, text: str) -> None:
        """An NPC line, post-gate. Already plain text — it never carried tags."""
        line = {"speaker": speaker, "text": text}
        with self._lock:
            self._spoken.append(line)
            self._push({"kind": "line", **line})

    def note(self, text: str) -> None:
        """Something the table should see that is not narration — an error, a notice."""
        with self._lock:
            self._push({"kind": "note", "text": text})

    def ended(self) -> None:
        """The evening is over. Watchers are told and their streams close.

        The flag outlives the message because a phone that reconnects afterwards must be
        told too — otherwise it waits all night on a session that finished, showing a
        screen that looks live.
        """
        with self._lock:
            self._ended = True
            self._push(ENDED)

    @property
    def acting(self) -> str:
        """Whose turn it is, as the last settled view said.

        The mirror is where the write route asks, because the mirror is what the devices
        were told. Asking the session instead would let a browser be refused for a reason
        no screen had shown it yet.
        """
        with self._lock:
            return self._table.acting if self._table else ""

    @property
    def party(self) -> set[str]:
        """Who is in this party, as the devices were told."""
        with self._lock:
            return {member.name for member in self._table.party} if self._table else set()

    @property
    def over(self) -> bool:
        with self._lock:
            return self._ended

    # --- what the server asks it -------------------------------------------

    def snapshot(self) -> dict:
        """Everything a device needs to draw the screen from cold, including mid-turn."""
        with self._lock:
            return {
                "kind": "table",
                "table": self._table.model_dump(mode="json") if self._table else None,
                "pending": self._pending,
                "spoken": list(self._spoken),
            }

    def subscribe(self) -> Watcher:
        watcher = Watcher()
        with self._lock:
            if self._ended:
                watcher.send(json.dumps(ENDED))
                return watcher
            self._watchers.append(watcher)
        return watcher

    def unsubscribe(self, watcher: Watcher) -> None:
        with self._lock:
            if watcher in self._watchers:
                self._watchers.remove(watcher)

    @property
    def watching(self) -> int:
        with self._lock:
            return len(self._watchers)

    # --- internals ---------------------------------------------------------

    def _push(self, message: dict) -> None:
        """Fan out to every watcher, dropping any that has stopped reading.

        Called with the lock held. A slow device is removed rather than waited for: the
        table is a real table, and a turn must not block on a browser.
        """
        body = json.dumps(message)
        self._watchers = [w for w in self._watchers if w.send(body)]
