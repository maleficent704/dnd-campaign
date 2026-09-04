"""Holding machine tags back from a live stream (P6.3, extracted from P1.3).

The GM's reply arrives a token at a time and carries `[[...]]` tags addressed to the
engine. `_clean` strips them from the finished text, but a *stream* has no finished text
yet — it has to decide about each character as it arrives, before it knows what follows.

This was one class inside the CLI, printing as it went, for three phases. It is here now
because Phase 6 gave it a second consumer, and that consumer is why it matters more than
it looks: **the streamed text is the one path to a player that does not go through the
view model.** `web/view.py` can guarantee that a `gm_only` fact never reaches a device
because there is nowhere in its types to put one — but a stream of raw model output goes
around that guarantee entirely, and `[[CANON: gm_only — the miller did it]]` is a real
string that a real GM emits mid-sentence. One filter, used by both front ends, is the
only version of this that stays true.

The filter is on `[[` rather than on each tag name. Every tag this project has added
since — `[[PROPOSE:`, `[[FACT:`, `[[SPEAK:`, `[[BELIEF:` — is the same kind of thing, and
a filter that must be updated per tag is one that eventually misses one in front of a
player.
"""

from __future__ import annotations

#: What opens a machine tag. Text is held from the first `[` and released as soon as it
#: cannot be the start of one, so ordinary bracketed prose still comes through.
MARKER = "[["


class TagStream:
    """Streamed GM text with machine tags withheld.

    `feed` returns what is safe to show; `finish` returns whatever was still being held.
    Neither writes anywhere — a caller prints it, buffers it, or pushes it down a socket.
    """

    def __init__(self) -> None:
        self._held = ""
        self._suppressing = False
        self._swallow = False

    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for char in chunk:
            if self._suppressing:
                self._held += char
                if self._held.endswith("]]"):
                    self._held = ""
                    self._suppressing = False
                    # Whatever whitespace followed the tag was there to space out the tag;
                    # the whitespace *before* it already went through, so keeping this too
                    # leaves a hole in the middle of the reply.
                    self._swallow = True
                continue

            if self._swallow:
                if char.isspace():
                    continue
                self._swallow = False

            if self._held or char == "[":
                self._held += char
                candidate = MARKER[: len(self._held)]
                if self._held.upper() == candidate:
                    if len(self._held) == len(MARKER):
                        self._suppressing = True
                    continue
                out.append(self._held)
                self._held = ""
                continue

            out.append(char)
        return "".join(out)

    def finish(self) -> str:
        """The tail, if it turned out not to be a tag after all.

        Idempotent: a caller may finish a stream more than once (an NPC line interrupting
        the GM's prose does exactly that) and only the first call can produce text.
        """
        tail = "" if self._suppressing else self._held
        self._held = ""
        return tail
