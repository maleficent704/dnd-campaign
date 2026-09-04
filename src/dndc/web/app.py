"""The read-only mirror, served over HTTP (P6.3).

Three routes and no write path. A device connected to this can watch an evening and can
do nothing else — which is the point of doing it before P6.4 rather than alongside it: the
secrecy boundary gets built and tested while there is still no concurrency to confuse it
with, and "what may this device be sent" is settled before "what may this device do".

**FastAPI is imported inside `build_app`, not at module scope.** The rules core, the CLI
and the whole test suite must still run on a machine that has no web extra installed, the
way they already run without `anthropic`. Importing it here would make Phase 6 a hard
dependency of `dndc roll`.
"""

from __future__ import annotations

import json
import queue
from pathlib import Path

from dndc.web.mirror import KEEPALIVE, Mirror

#: The page, as a file rather than a string in Python. No build step and no template
#: engine: it is one document, it is read once, and a diff of it should read as HTML.
PAGE = Path(__file__).resolve().parent / "page.html"

#: How long a watcher waits for a message before the stream sends a keepalive instead.
#: Also the ceiling on how long a shutdown takes to be noticed.
POLL_SECONDS = 15.0


class WebNotInstalled(RuntimeError):
    """The `web` extra is not installed. Raised with the command that fixes it."""


def build_app(mirror: Mirror):
    """A FastAPI app serving one mirror.

    Takes the mirror rather than making one: the session owns it, the server borrows it,
    and there is exactly one so a second front end cannot start a second campaign.
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, StreamingResponse
    except ImportError as exc:  # pragma: no cover - exercised by hand, not in CI
        raise WebNotInstalled(
            "the web front end needs the `web` extra: pip install -e .[web]"
        ) from exc

    app = FastAPI(title="dndc", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/table")
    def table() -> dict:
        """The whole screen, from cold. Everything a device needs and nothing else."""
        return mirror.snapshot()

    @app.get("/api/events")
    def events():
        """Server-sent events: the snapshot, then every change as it happens.

        The snapshot goes first so a device that connects mid-turn draws a correct screen
        rather than an empty one that fills in from the next event onward.
        """

        def stream():
            watcher = mirror.subscribe()
            try:
                yield _sse(json.dumps(mirror.snapshot()))
                while True:
                    try:
                        message = watcher.queue.get(timeout=POLL_SECONDS)
                        yield _sse(message)
                        if json.loads(message).get("kind") == "ended":
                            # The session is over. Closing beats leaving a socket open on
                            # a campaign that has stopped: a browser showing a live screen
                            # for a finished evening is worse than one showing none.
                            return
                    except queue.Empty:
                        # A comment frame: keeps a proxy or a sleeping phone from closing
                        # a connection that everybody involved believes is still open.
                        yield f": {KEEPALIVE}\n\n"
            finally:
                mirror.unsubscribe(watcher)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _sse(body: str) -> str:
    return f"data: {body}\n\n"
