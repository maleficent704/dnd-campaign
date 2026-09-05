"""The LAN gate: one shared token, and a careful account of what it is not (P6.7b).

Kelly ruled this on 2026-09-04, against the per-session code `docs/LAN-ACCESS.md` used to
recommend: **a fixed token in the gitignored `.env`**, matching `the-room`'s `ROOM_TOKEN`.
The reasoning is in that file and worth not re-deriving — a rotating code has to be read
off a terminal and re-sent to two people every evening, on a page a family is meant to
bookmark, and it defends against an attacker who does not exist here at the cost of the
thing that made hosting worth doing.

**This is not authentication and must never be described as one.** There is no identity
here and P6.7b does not add one: everyone holding the token is the same person as far as
this server is concerned, exactly as "There is no login" in `docs/LAN-ACCESS.md` says. What
it stops is a device that found the port. That is the actual threat once the exposure stops
being an evening somebody started in the room and becomes a service that answers all the
time, and it is the whole of what this buys.

**Why a cookie and not a header.** `the-room` takes `Authorization: Bearer`, and so does
this — but a browser cannot put a header on an `EventSource`, and the event stream is where
the narration actually flows. Gating the write routes while leaving the stream open would
be a gate around the door of a room with no wall. So a token may arrive three ways: the
header (scripts, curl, and the house's own precedent), `?k=` in the URL (the bookmark
Kelly asked for), or the cookie the page is given when a valid `?k=` arrives. The page's
own `fetch` and `EventSource` calls are same-origin and relative, so the cookie rides along
on both without the page having to know the gate exists.

**When it is mandatory.** Not always, and the exception is deliberate. `dndc play --serve`
on kelly-pc, bound to the LAN, lasting one evening, started by somebody in the room, is the
posture this house has chosen for every service on the LAN and P6.6 documented it as such.
Forcing a token there would break the evening Kelly and Sam actually play in exchange for
nothing. A token is *required* when the exposure is larger than that — a wildcard bind,
which P6.6 measured reaches the tailnet, or the hosted service, which never stops. In both
of those cases an absent token is a refusal to start, not a shrug: a service that quietly
drops its only control is the P6.6 firewall again, reporting success and protecting
nothing.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from dndc.config import MIN_WEB_TOKEN, WEB_REQUIRE_TOKEN_ENV, WEB_TOKEN_ENV

#: The cookie the page is handed once it presents a valid token, so that the event stream
#: — which cannot carry a header — is covered by the same gate as everything else.
COOKIE = "dndc_table"

#: The query parameter, which is the bookmark: `http://host:port/?k=TOKEN`.
QUERY = "k"


class TokenError(RuntimeError):
    """A token was required and there wasn't a usable one. Raised with the fix."""


def configured_token() -> str | None:
    """The token from the environment, or None.

    Environment only — never `config.yaml`. That file is committed, and a token in it
    would be a committed secret, which is the one rule this house does not bend. `.env` is
    gitignored and reaches a container through `env_file:`; see `.env.example`.
    """
    token = os.environ.get(WEB_TOKEN_ENV, "").strip()
    return token or None


def deployment_requires() -> bool:
    """Whether the deployment has declared this exposure too big to run open.

    A separate variable from the token itself, and that is the point: a typo in the
    token's *name* would otherwise mean an ungated service that started cleanly. With two
    variables, the deployment asserts the requirement and the code checks it, so a missing
    token fails loudly instead of being indistinguishable from a table that never wanted
    one. `the-room`'s bind address plus `DOCKER-USER` is the same control-and-belt shape.
    """
    return os.environ.get(WEB_REQUIRE_TOKEN_ENV, "").strip().lower() not in (
        "", "0", "false", "no",
    )


def resolve_gate(required: bool) -> Gate:
    """The gate this server will run behind, refusing rather than degrading.

    `required=True` is the caller saying the exposure is bigger than one evening on the
    LAN. A missing or too-short token is then an error and not a warning, because the
    alternative is a service that comes up looking fine with its only control absent.
    """
    token = configured_token()
    if not required:
        return Gate(token)
    if token is None:
        raise TokenError(
            f"no {WEB_TOKEN_ENV} — this exposure needs one. Put a long random string in "
            f".env (see .env.example); refusing to serve without a gate."
        )
    if len(token) < MIN_WEB_TOKEN:
        raise TokenError(
            f"{WEB_TOKEN_ENV} is {len(token)} characters; use at least {MIN_WEB_TOKEN}. "
            "A token short enough to guess is worse than none, because it reads as a "
            "control while being one."
        )
    return Gate(token)


@dataclass(frozen=True)
class Gate:
    """Whether a request gets in, and by what.

    `token=None` is genuinely open, and that is a state the callers name out loud rather
    than arrive at by accident: `resolve_gate` will not return it when a token is
    required, and the CLI says so on the startup line when it does.
    """

    token: str | None

    @property
    def guarded(self) -> bool:
        return self.token is not None

    def admits(
        self,
        header: str | None = None,
        cookie: str | None = None,
        query: str | None = None,
    ) -> bool:
        """True if this request may proceed.

        Compared with `hmac.compare_digest` rather than `==` so a wrong token cannot be
        narrowed down a character at a time by timing the reply — the same care
        `the-room` takes, and cheap enough that not taking it would be a choice.
        """
        if not self.guarded:
            return True
        offered = first_offered(header, cookie, query)
        if not offered:
            return False
        return hmac.compare_digest(offered, self.token or "")


def token_from_header(authorization: str | None) -> str | None:
    """The token out of an `Authorization` header, with or without the scheme.

    `Bearer <token>` is the standard; a script that sends the bare token should get in
    rather than get a 401 nobody can debug. Lifted from `the-room`, where the same
    tolerance is already paid for.
    """
    if not authorization:
        return None
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value.split(None, 1)[1].strip()
    return value or None


def first_offered(
    header: str | None = None,
    cookie: str | None = None,
    query: str | None = None,
) -> str | None:
    """The token a request carries, wherever it chose to carry it.

    Order is header, then cookie, then query — most explicit first, so a stale cookie in a
    browser cannot quietly override a token a script meant to use.
    """
    for candidate in (token_from_header(header), (cookie or "").strip(), (query or "").strip()):
        if candidate:
            return candidate
    return None
