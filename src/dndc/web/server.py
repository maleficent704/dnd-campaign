"""Running the mirror beside a session (P6.3).

The server runs in a daemon thread next to the play loop rather than the other way round,
and that is a deliberate ordering: **the evening is the process, and the web is a thing it
is also doing.** A crash in the server must not take the table down, a browser must not be
able to hold up a turn, and closing the terminal must end everything — which a daemon
thread gives for free.

`dndc serve` as a standalone command belongs to P6.6, where the bind address becomes a
config question rather than a flag.
"""

from __future__ import annotations

import socket
import threading

from dndc.web.mirror import Mirror

#: Bound to every interface on purpose: the whole point is the other sofa. What that does
#: and does not protect is written down in P6.6 rather than assumed here.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765


class Server:
    """A uvicorn instance in a thread, and the address to tell people about."""

    def __init__(self, mirror: Mirror, host: str, port: int) -> None:
        self.mirror = mirror
        self.host = host
        self.port = port
        self._thread: threading.Thread | None = None
        self._server = None

    @property
    def url(self) -> str:
        """The address to read out loud, which is never `0.0.0.0`."""
        return f"http://{lan_address() if self.host == DEFAULT_HOST else self.host}:{self.port}"

    def start(self) -> None:
        import uvicorn

        from dndc.web.app import build_app

        config = uvicorn.Config(
            build_app(self.mirror),
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
