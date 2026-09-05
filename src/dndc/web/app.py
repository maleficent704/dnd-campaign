"""The read-only mirror, served over HTTP (P6.3).

Three routes and no write path. A device connected to this can watch an evening and can
do nothing else — which is the point of doing it before P6.4 rather than alongside it: the
secrecy boundary gets built and tested while there is still no concurrency to confuse it
with, and "what may this device be sent" is settled before "what may this device do".

**FastAPI is imported inside `build_app`, not at module scope.** The rules core, the CLI
and the whole test suite must still run on a machine that has no web extra installed, the
way they already run without `anthropic`. Importing it here would make Phase 6 a hard
dependency of `dndc roll`.

**The gate arrived in P6.7b** and is checked on every route that carries the campaign,
including the event stream — see `web/gate.py` for why the stream is the one that made a
cookie necessary, and `docs/LAN-ACCESS.md` for why it is not authentication.
"""

# Deliberately NO `from __future__ import annotations` in this module. FastAPI resolves a
# route's annotations by name against the *module's* globals, and `Request` is imported
# inside `build_app` so that fastapi stays off the import path of `dndc roll` (see below).
# With postponed evaluation those annotations are strings that resolve to nothing, and
# FastAPI silently reads `request: Request` as a body field — every route still answers,
# with the wrong thing. Evaluated eagerly, the annotation is the local class and it works.

import json
import queue
from pathlib import Path

from dndc.web.gate import COOKIE, QUERY, Gate
from dndc.web.mirror import KEEPALIVE, Mirror

#: The page, as a file rather than a string in Python. No build step and no template
#: engine: it is one document, it is read once, and a diff of it should read as HTML.
PAGE = Path(__file__).resolve().parent / "page.html"

#: What somebody without the token is shown. A file for the same reason `page.html` is
#: one: the wording is the whole of it, and it should be editable without touching Python.
CLOSED = Path(__file__).resolve().parent / "closed.html"

#: How long a browser keeps the cookie. Long, because the point of a fixed token is a
#: bookmark that keeps working — a gate that quietly expires is a gate somebody has to be
#: told about again every few weeks, which is the per-session code by another route.
COOKIE_SECONDS = 365 * 24 * 60 * 60

#: How long a watcher waits for a message before the stream sends a keepalive instead.
#: Also the ceiling on how long a shutdown takes to be noticed.
POLL_SECONDS = 15.0


class WebNotInstalled(RuntimeError):
    """The `web` extra is not installed. Raised with the command that fixes it."""


def build_app(mirror: Mirror, floor=None, gate: Gate | None = None):
    """A FastAPI app serving one mirror, and optionally taking turns for one floor.

    Takes both rather than making either: the session owns them, the server borrows them,
    and there is exactly one of each so a second front end cannot start a second campaign.

    `floor=None` is a genuinely read-only server, and it is not a degraded mode — it is
    what `--serve` gave before P6.4 and what a spectator link should still give. The write
    route does not exist when there is no floor, rather than existing and refusing, so a
    device cannot tell the difference between "not allowed" and "not built".

    `gate=None` is an open table, which is what an evening on the LAN has always been and
    still is (P6.6's posture, and `docs/LAN-ACCESS.md`). It is not the same shape as
    `floor=None`: a gate that is absent must still leave every route present, because
    which routes exist is a fact about the *session*, and who may reach them is a fact
    about the *exposure*. Collapsing the two would mean a hosted spectator link quietly
    becoming unauthenticated the moment somebody turned the token off.
    """
    gate = gate or Gate(None)
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    except ImportError as exc:  # pragma: no cover - exercised by hand, not in CI
        raise WebNotInstalled(
            "the web front end needs the `web` extra: pip install -e .[web]"
        ) from exc

    app = FastAPI(title="dndc", docs_url=None, redoc_url=None)

    def admitted(request: Request) -> bool:
        """Whether this request carries the token, however it chose to carry it.

        Read off the request rather than declared per route, so adding a route cannot
        accidentally add an ungated one — the same reasoning as P6.7a's single resolution
        point. A route that forgets to call this is a route somebody has to notice.
        """
        return gate.admits(
            header=request.headers.get("authorization"),
            cookie=request.cookies.get(COOKIE),
            query=request.query_params.get(QUERY),
        )

    def refused() -> JSONResponse:
        """A refusal that says what would fix it, without saying whether a token existed.

        Deliberately the same answer for "no token" and "wrong token". Telling the two
        apart is free reconnaissance and buys a legitimate device nothing: whoever is
        meant to be here has the link.
        """
        return JSONResponse(
            {"error": "this table is closed", "how": "open the link with ?k=… in it"},
            status_code=401,
        )

    def snapshot() -> dict:
        """The mirror's state, plus whether this server takes turns.

        The device is told rather than left to find out by trying. A page that probes by
        POSTing an empty turn works, but it means every spectator link starts by making a
        request designed to be refused — and a screen should not have to guess at what it
        is connected to.
        """
        return {**mirror.snapshot(), "writable": floor is not None}

    @app.get("/", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        """The page, and the one place a token in a URL becomes a cookie.

        The cookie is what covers the event stream: a browser cannot put a header on an
        `EventSource`, and gating the write routes while leaving the narration streaming
        to anybody would be a gate around the door of a room with no wall. Because the
        page's own calls are same-origin and relative, the cookie rides along on both
        `fetch` and `EventSource` without the page knowing the gate exists.

        `HttpOnly`, because nothing in the page needs to read it, and `SameSite=Lax`, so
        another site cannot make a browser spend it.
        """
        if not admitted(request):
            return HTMLResponse(CLOSED.read_text(encoding="utf-8"), status_code=401)
        response = HTMLResponse(PAGE.read_text(encoding="utf-8"))
        offered = (request.query_params.get(QUERY) or "").strip()
        if gate.guarded and offered:
            response.set_cookie(
                COOKIE,
                offered,
                max_age=COOKIE_SECONDS,
                httponly=True,
                samesite="lax",
                path="/",
            )
        return response

    @app.get("/api/table")
    def table(request: Request):
        """The whole screen, from cold. Everything a device needs and nothing else."""
        if not admitted(request):
            return refused()
        return snapshot()

    if floor is not None:

        @app.post("/api/turn")
        def turn(body: dict, request: Request) -> JSONResponse:
            """Say something, if it is your turn.

            This does **not** run a turn. It puts a line on the floor's queue and returns;
            the play loop picks it up on its own thread, exactly as it picks up a line
            from the keyboard. Every piece of campaign state this project owns — the
            engine, the canon store, the save point — is single-threaded by construction,
            and a turn run from a request handler would be a race against the campaign.

            A refusal is answered plainly rather than swallowed. A device in another room
            that has its sentence quietly dropped has no way to find that out.
            """
            if not admitted(request):
                return refused()
            offer = floor.offer(
                character=str(body.get("character", "")),
                text=str(body.get("text", "")),
                acting=mirror.acting,
                party=mirror.party,
            )
            if offer.accepted:
                return JSONResponse({"accepted": True}, status_code=202)
            return JSONResponse(
                {"accepted": False, "refusal": offer.refusal.value, "reason": offer.reason},
                status_code=409,
            )

        @app.post("/api/answer")
        def answer(body: dict, request: Request) -> JSONResponse:
            """Answer the question the table is being asked.

            Not gated on whose turn it is: a confirmation belongs to the table, not to the
            acting player. Either of them may say whether an item goes on a sheet.
            """
            if not admitted(request):
                return refused()
            offer = floor.answer(str(body.get("text", "")))
            if offer.accepted:
                return JSONResponse({"accepted": True}, status_code=202)
            return JSONResponse(
                {"accepted": False, "refusal": offer.refusal.value, "reason": offer.reason},
                status_code=409,
            )

    @app.get("/api/events")
    def events(request: Request):
        """Server-sent events: the snapshot, then every change as it happens.

        The snapshot goes first so a device that connects mid-turn draws a correct screen
        rather than an empty one that fills in from the next event onward.

        Gated like everything else, and this is the route that made the cookie necessary:
        the narration flows here, so a stream anybody could open would make the gate on
        the write routes decorative.
        """
        if not admitted(request):
            return refused()

        def stream():
            watcher = mirror.subscribe()
            try:
                yield _sse(json.dumps(snapshot()))
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
