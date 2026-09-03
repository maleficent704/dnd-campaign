"""Rebuilding a played session from its log.

The JSONL log is append-only and complete (D-008), so a finished session can be read back
into the `Turn` objects the memory layers consume. Everything in `analysis/` starts here,
and so did three throwaway scripts before this module existed — which is the repo saying
where it belonged.

**Narration is cleaned exactly as it was on the night.** The logged text still carries the
`[[CHECK]]`, `[[CANON]]` and `[[GAIN/LOSE]]` tags, because the log records what the model
actually said. Replaying without stripping them would feed a transcript to the sweep and
the chronicle that no player ever saw and that the GM never had in its own window — the
measurement would be of a session that did not happen.

**A pending narration is not a turn.** Model calls log intent before the call (OD-9), so a
crashed session leaves a `pending` row with no text. Replay takes terminal rows only.

**One log can span a restart.** Since P5.1 a session that crashed is resumed into its own
file and writes a second `session_meta` header there. The turns either side of it are one
session and read as one, but the provenance is not interchangeable: the halves may have run
at different commits, under a different billing seat, on a different seed. `commit_sha` is
what the session *started* at, `commits` is everything that wrote into it, and `restarts`
says how many times the process came back. A replay that quietly took the last header would
attribute the whole evening to whichever code happened to finish it.

**Character creation is not play.** P1.4 reuses `gm_narration` with `scene: "character
creation"` rather than adding an event family, and the P1.4 handoff called that scene field
"an adequate discriminator for Phase 7 filtering". This is that filtering: an interview
about what a character should be like establishes nothing about the world, and a drift
measurement that counted it would be measuring the wrong conversation. Found by the first
live run of the drift instrument, on an archived fixture that turned out to be Sam building
Brother Hammond.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from dndc.game.creation import CREATION_SCENE
from dndc.gm.canontag import find_canon_tags, strip_canon_tags
from dndc.gm.checkrequest import strip_check_requests
from dndc.gm.context import Turn
from dndc.gm.inventorytag import strip_inventory_tags
from dndc.logging import read_log
from dndc.schema.events import CallStatus, EventType


def clean(text: str) -> str:
    """Narration as the table saw it — every machine tag removed.

    Deliberately the same three strippers `game/turn.py::_clean` applies, in the same
    order. If they ever disagree, the analysis is measuring a different text than the one
    the campaign ran on.
    """
    return strip_inventory_tags(strip_canon_tags(strip_check_requests(text)))


@dataclass
class ReplayedSession:
    """One logged session, rebuilt."""

    path: Path
    turns: list[Turn] = field(default_factory=list)
    session_id: str | None = None
    campaign: str | None = None
    #: The commit the session **started** at. A restart may have landed on another one;
    #: see `commits`.
    commit_sha: str | None = None
    #: Every distinct commit that wrote into this log, in the order they appeared. One
    #: entry for a session that ran straight through, more when it was restarted onto
    #: changed code — which a replay must not average away, because the whole point of
    #: stamping the SHA is being able to say which code produced which turn.
    commits: tuple[str, ...] = ()
    #: Process restarts inside this one session (P5.1/P5.2): extra `session_meta` rows.
    #: Zero for every log written before 2026-09-03.
    restarts: int = 0
    #: The session this one was picked up from, if it was. Self-referential when a
    #: crashed session resumed into its own log.
    resumed_from: str | None = None
    #: Facts the GM declared inline, in order, paired with the turn index they landed on.
    #: Empty for any session logged before P2.2 (2026-08-10) — which is what makes those
    #: logs the before-picture the drift test needs.
    tagged: list[tuple[int, str]] = field(default_factory=list)

    @property
    def party(self) -> tuple[str, ...]:
        """Characters who spoke, in first-appearance order."""
        seen: list[str] = []
        for turn in self.turns:
            name = _character(turn.speaker)
            if name and name not in seen:
                seen.append(name)
        return tuple(seen)


def replay(path: Path | str) -> ReplayedSession:
    """Read a session log back into turns, with the metadata that says what it was."""
    target = Path(path)
    session = ReplayedSession(path=target)
    pending_input = ""
    speaker = ""

    for event in read_log(target):
        if event.type is EventType.SESSION_META:
            # A resumed session writes a second header into the same file (D-008 item
            # 27). The first row is the session's own provenance and later ones must not
            # overwrite it: the turns before the restart really did run at that commit.
            if session.session_id is None:
                session.session_id = event.session_id
                session.campaign = event.campaign
                session.commit_sha = event.commit_sha
                session.resumed_from = event.resumed_from
            else:
                session.restarts += 1
            if event.commit_sha and event.commit_sha not in session.commits:
                session.commits = session.commits + (event.commit_sha,)
        elif event.type is EventType.PLAYER_INPUT:
            pending_input = event.text
            speaker = (
                f"{event.player} ({event.character})" if event.character else event.player
            )
        elif event.type is EventType.GM_NARRATION and event.status is CallStatus.COMPLETE:
            if event.scene == CREATION_SCENE:
                # Not play. See the module docstring.
                pending_input = ""
                speaker = ""
                continue
            narration = clean(event.text)
            if not narration:
                # A reply that was nothing but a check request. It happened, but it
                # established nothing and reads as an empty exchange.
                continue
            for tag in find_canon_tags(event.text):
                session.tagged.append((len(session.turns), tag.text))
            session.turns.append(
                Turn(
                    player_input=pending_input,
                    narration=narration,
                    speaker=speaker,
                    opening=not pending_input,
                )
            )
            pending_input = ""
            speaker = ""

    return session


def replay_turns(paths: Sequence[Path | str]) -> list[Turn]:
    """Several logs as one run of turns, in the order given."""
    turns: list[Turn] = []
    for path in paths:
        turns.extend(replay(path).turns)
    return turns


def _character(speaker: str) -> str | None:
    """"Kelly (Corin Vale)" -> "Corin Vale". The player's name is not a character."""
    if "(" not in speaker or not speaker.endswith(")"):
        return None
    return speaker[speaker.index("(") + 1 : -1].strip() or None
