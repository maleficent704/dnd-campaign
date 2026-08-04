"""Append-only JSONL event emitter and cost telemetry (D-008).

**On the name.** This package is `dndc.logging`, which shadows the stdlib `logging`
*only* for the expression `from dndc import logging`. Python 3 has no implicit relative
imports, so an absolute `import logging` anywhere — including inside this package —
resolves to the standard library as normal. Confirmed by test (P0.5, owed to Fable's
2026-07-27 ruling); the layout comes from CLAUDE.md and is kept.
"""

from dndc.logging.emitter import (
    SessionLog,
    events_of,
    git_commit_sha,
    iter_raw,
    new_session_id,
    next_seq_for,
    read_log,
    resolve_log_dir,
)

__all__ = [
    "SessionLog",
    "events_of",
    "git_commit_sha",
    "iter_raw",
    "new_session_id",
    "next_seq_for",
    "read_log",
    "resolve_log_dir",
]
