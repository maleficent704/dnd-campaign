"""Running the mirror beside a session (P6.3).

The server runs in a daemon thread next to the play loop rather than the other way round,
and that is a deliberate ordering: **the evening is the process, and the web is a thing it
is also doing.** A crash in the server must not take the table down, a browser must not be
able to hold up a turn, and closing the terminal must end everything — which a daemon
thread gives for free.

**The bind address comes from config and defaults to the LAN, not to every interface**
(P6.6). It used to be `0.0.0.0`, with a comment saying what that exposed would be written
down here rather than assumed. Writing it down is what changed it: this house has already
measured that a wildcard bind is *not* LAN-only, because the machine is a Tailscale node
and `tailscale0` is one of the interfaces `0.0.0.0` means — see `docs/LAN-ACCESS.md` and
race-control `operations/lan-only-services.md`. A table with no login should be reachable
from the other sofa and not from a phone on cellular.
"""

from __future__ import annotations

import socket
import threading

from dndc.config import EVERY_INTERFACE, LAN

#: Binds that mean "every interface", and therefore also the tailnet.
WILDCARD = frozenset({EVERY_INTERFACE, "::", "*"})


def resolve_host(host: str) -> str:
    """`lan` becomes this machine's LAN address; anything else is taken at its word."""
    cleaned = host.strip()
    return lan_address() if cleaned.lower() == LAN else cleaned


def is_everywhere(host: str) -> bool:
    """Whether a configured host means every interface — the tailnet included.

    A module function rather than only a property, because the caller has to know this
    *before* it builds a server: a wildcard bind is one of the two exposures that make the
    P6.7b token mandatory, and refusing to start is not something to discover after the
    socket is open.
    """
    return resolve_host(host) in WILDCARD


class Server:
    """A uvicorn instance in a thread, and the address to tell people about."""

    def __init__(self, evenings, host: str, port: int, gate=None) -> None:
        #: The evening this server is showing, if it is showing one — a `Lifecycle` for a
        #: hosted server that can start one, or a `Held` for a `dndc play --serve` whose
        #: evening the CLI already owns (P6.7b-iii). The mirror and floor come off this
        #: per request rather than being held here, because a hosted server gets a fresh
        #: pair every evening.
        self.evenings = evenings
        #: The LAN gate (P6.7b), or None for an open table. Resolved by the caller,
        #: because whether a token is *required* is a fact about the exposure and the
        #: deployment, not about this class.
        self.gate = gate
        #: What was asked for (`lan`, an address, `0.0.0.0`) — kept so a message can say
        #: what the table chose rather than only what it resolved to.
        self.requested = host
        self.host = resolve_host(host)
        self.port = port
        self._thread: threading.Thread | None = None
        self._server = None

    @property
    def url(self) -> str:
        """The address to read out loud, which is never `0.0.0.0`."""
        return f"http://{lan_address() if self.everywhere else self.host}:{self.port}"

    @property
    def everywhere(self) -> bool:
        """True when this is bound to every interface — the tailnet included."""
        return self.host in WILDCARD

    @property
    def guarded(self) -> bool:
        """True when a token is needed to reach this (P6.7b)."""
        return self.gate is not None and self.gate.guarded

    def start(self) -> None:
        import uvicorn

        from dndc.web.app import build_app

        config = uvicorn.Config(
            build_app(self.evenings, self.gate),
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            # Short: the thread is a daemon and the process is ending anyway. Waiting on a
            # web server to notice it should stop is not something a table should do.
            self._thread.join(timeout=2.0)


def lan_address() -> str:
    """This machine's address on the LAN, for reading out to somebody on the sofa.

    Found by asking the routing table which interface would reach the outside — no packet
    is sent. `gethostbyname` was wrong here: on a machine with a VPN or several adapters
    it cheerfully returns the one nobody can reach.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 1))  # TEST-NET-1: reserved, routable, never answers
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()
