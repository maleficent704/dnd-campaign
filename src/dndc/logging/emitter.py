"""Append-only JSONL session log (D-008).

One file per session, one JSON object per line, opened in append mode and flushed on
every write. Nothing here ever rewrites or truncates a line that has been written: the
log is the research record, and a mutated log is a corrupted experiment.

`seq` is monotonic within a session and is assigned here rather than by callers, so two
components cannot race to the same number. Reopening an existing log resumes the counter
from the highest `seq` already on disk — the `seq`-continuity rider ported from
npc-village, which otherwise bites the first time a process restarts mid-session.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import TypeAdapter

from dndc.schema.events import Event, EventType, _Event, utcnow

E = TypeVar("E", bound=_Event)

_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def git_commit_sha(repo: Path | None = None) -> tuple[str | None, bool]:
    """Return (commit sha, dirty). Both None/False outside a git repo.

    Stamped into `session_meta` every session — the mystery's lesson. The dirty flag
    matters as much as the SHA: with uncommitted changes the SHA does not describe the
    code that actually ran, so a replay claim based on it would be false.
    """
    cwd = str(repo) if repo else None
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None, False
    return (sha or None), bool(status)


def new_session_id(now: datetime | None = None) -> str:
    return (now or utcnow()).strftime("%Y%m%d-%H%M%S")


class SessionLog:
    """Writer for one session's event stream."""

    def __init__(self, path: Path, session_id: str, start_seq: int = 0) -> None:
        self.path = Path(path)
        self.session_id = session_id
        self._seq = start_seq
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def open(cls, log_dir: Path, session_id: str | None = None) -> SessionLog:
        """Open a session log under `log_dir`, or resume a named one.

        Naming a `session_id` means *resume that session*: the file is reopened and `seq`
        continues from the highest already in it (P5.1 does this when a save point is
        picked up after a crash). Not naming one means a new session, and a new session
        must never land inside an existing file — ids are second-resolution, so two runs
        started in the same second would otherwise silently share a record and the log
        would show one session that had inexplicably restarted.
        """
        if session_id is None:
            session_id = _free_session_id(Path(log_dir))
        path = Path(log_dir) / f"{session_id}.jsonl"
        return cls(path, session_id, start_seq=next_seq_for(path))

    @property
    def seq(self) -> int:
        """The seq the next emitted event will receive."""
        return self._seq

    def emit(self, event_type: type[E], **fields) -> E:
        """Build, write, and return one event. `seq`/`session_id` are filled in here."""
        event = event_type(seq=self._seq, session_id=self.session_id, **fields)
        self._write(event)
        self._seq += 1
        return event

    def _write(self, event: _Event) -> None:
        line = json.dumps(
            event.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
        )
        # Append + flush + fsync-free: durable enough for a play session, and the append
        # mode is what guarantees we cannot clobber earlier turns.
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()

    def __repr__(self) -> str:
        return f"SessionLog(path={self.path.name!r}, session={self.session_id!r}, seq={self._seq})"


def _free_session_id(log_dir: Path) -> str:
    """A session id with no file already under it. Suffixed rather than timestamped
    finer, because the id is read by humans and `-2` says what happened."""
    base = new_session_id()
    candidate, attempt = base, 1
    while (log_dir / f"{candidate}.jsonl").exists():
        attempt += 1
        candidate = f"{base}-{attempt}"
    return candidate


def next_seq_for(path: Path) -> int:
    """Highest `seq` on disk + 1, or 0 for a new/absent log."""
    path = Path(path)
    if not path.exists():
        return 0
    highest = -1
    for record in iter_raw(path):
        seq = record.get("seq")
        if isinstance(seq, int) and seq > highest:
            highest = seq
    return highest + 1


def iter_raw(path: Path) -> Iterator[dict]:
    """Yield raw JSON objects, skipping blank lines.

    Deliberately tolerant: a truncated final line from a hard crash must not make the
    rest of the session unreadable.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_log(path: Path) -> list[Event]:
    """Parse a session log into typed events (Phase 7 analysis reads through this)."""
    return [_EVENT_ADAPTER.validate_python(record) for record in iter_raw(path)]


def events_of(path: Path, event_type: EventType) -> list[Event]:
    return [e for e in read_log(path) if e.type == event_type]


def resolve_log_dir(configured: str, root: Path | None = None) -> Path:
    """Resolve the configured log directory against the repo root unless absolute."""
    candidate = Path(os.path.expanduser(configured))
    if candidate.is_absolute():
        return candidate
    base = root or Path(__file__).resolve().parents[3]
    return base / candidate
