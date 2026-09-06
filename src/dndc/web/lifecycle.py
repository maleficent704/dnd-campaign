"""The evening this server is running, if it is running one (P6.7b-iii).

Until now the evening *was* the process. `dndc play --serve` built one, served it, and
exited when it ended; `dndc serve` was the same thing with one default flipped. That is
the right shape for a laptop on the table and the wrong shape for a container, which
boots with nobody playing, has to show something anyway, and must still be running
tomorrow.

So this inverts the ownership for the hosted case only: **the server is the process, and
an evening is a thing it is also doing.** `dndc play --serve` keeps the old shape exactly
— it is still the evening that owns the process there, and this class simply holds the
one evening that was already started.

**One at a time, and that is a rule rather than a limitation.** Every piece of campaign
state this project owns is single-threaded by construction (P6.4), and two evenings would
be two writers on one canon ledger. A second `start` while one is running is refused with
a sentence, not queued.

**A fresh `Mirror` and `Floor` per evening**, which is why the app resolves them through
this object on every request rather than closing over them at build time — the P6.7a
lesson, in a second place. A `Mirror` is deliberately one-shot: once it has said the
evening ended, a watcher that reconnects is told so immediately, which is correct for a
process that is about to exit and a reconnect loop for one that is not. Installing a new
empty mirror when the evening finishes is what turns that loop back into a start screen.
"""

from __future__ import annotations

import argparse
import copy
import threading
from dataclasses import dataclass
from typing import Callable

from dndc.game.campaign import list_campaigns
from dndc.game.evening import run_evening
from dndc.game.floor import Floor
from dndc.game.setup import Herald, QuietHerald, SetupError, build_evening
from dndc.web.mirror import Mirror

#: Nobody is playing. Either nothing has started yet, or the last evening finished.
IDLE = "idle"

#: Somebody asked for an evening and it is being built — the recap alone can take a
#: minute or two, and a page that showed "idle" through all of it would invite a second
#: click on a button that is already working.
STARTING = "starting"

#: An evening is running and the floor is taking lines.
PLAYING = "playing"


@dataclass(frozen=True)
class Started:
    """Whether an evening was started, and what to say if not."""

    accepted: bool
    reason: str = ""


class Lifecycle:
    """One server's evening: none, starting, or running.

    `table_for` builds the `Table` the session talks to. It is injected rather than
    imported because every implementation of it lives in the CLI, next to `rich` — and a
    web module that imported the CLI to draw a table would be the dependency arrow
    pointing the wrong way.
    """

    def __init__(
        self,
        cfg,
        args: argparse.Namespace,
        *,
        table_for: Callable,
        herald: Herald | None = None,
        commands: Callable | None = None,
        keyboard_for: Callable | None = None,
        build=build_evening,
        run=run_evening,
    ) -> None:
        self._cfg = cfg
        self._args = args
        self._table_for = table_for
        self._herald = herald or QuietHerald()
        self._commands = commands
        #: Starts a terminal reader on the floor, when there is a terminal. `dndc serve`
        #: run by hand keeps its hot seat this way; the container passes nothing and the
        #: evening simply has one fewer source, which is what `_keyboard` always said.
        self._keyboard_for = keyboard_for
        self._build = build
        self._run = run

        self._lock = threading.Lock()
        self._mirror = Mirror()
        self._floor: Floor | None = None
        self._phase = IDLE
        self._campaign = ""
        self._error = ""
        self._thread: threading.Thread | None = None

    # --- what the server asks it -------------------------------------------

    @property
    def mirror(self) -> Mirror:
        """The mirror of the evening currently running, or an empty one.

        Never `None`, so a route never has to branch on whether anything is happening —
        an idle mirror snapshots as a screen with no table on it, which is exactly what a
        start screen wants to draw over.
        """
        with self._lock:
            return self._mirror

    @property
    def floor(self) -> Floor | None:
        """The floor taking lines, or `None` when nothing is running.

        `None` here means the same thing it means in `build_app`: there is nothing to
        say a line *to*. It is not the spectator case — that one is still decided when
        the evening starts.
        """
        with self._lock:
            return self._floor

    @property
    def can_manage(self) -> bool:
        """Whether this server should build the start/end routes at all.

        True: starting an evening is the whole reason this class exists. `Held` says no,
        which is what keeps `dndc play --serve` exactly the app it was — see there.
        """
        return True

    @property
    def can_play(self) -> bool:
        """Whether this server should build write routes at all.

        Asked once, when the app is built, because a route table cannot be rebuilt
        between evenings. True here: a hosted server can start a playable evening even
        while it is sitting idle, so the routes must exist for the evening it has not
        started yet. `Held` is where this can be false, and that is what keeps P6.3's
        spectator link route-less rather than merely refused.
        """
        return not getattr(self._args, "watch_only", False)

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    def state(self) -> dict:
        """What the page needs to know that is not the table itself."""
        with self._lock:
            return {
                "phase": self._phase,
                "campaign": self._campaign,
                "error": self._error,
            }

    def campaigns(self) -> list[dict]:
        """What there is to play, for the start screen.

        Read on request rather than cached: `dndc create-character` on the host makes a
        campaign appear, and a hosted server should not need restarting to notice.
        """
        return [
            {"slug": campaign.slug, "name": campaign.name, "players": list(campaign.players)}
            for campaign in list_campaigns()
        ]

    # --- what a browser asks it --------------------------------------------

    def start(self, campaign: str, *, watch_only: bool = False) -> Started:
        """Build and run an evening on a thread of its own.

        The mirror and floor are installed **before** the thread starts, so a device that
        connects during the minute the recap takes is watching the evening it asked for
        rather than the last one. Construction happens on the thread because it is slow
        and a request must not wait on a 70B waking up.
        """
        slug = (campaign or "").strip()
        if not slug:
            return Started(False, "name a campaign")

        with self._lock:
            if self._phase != IDLE:
                return Started(False, f"an evening is already {self._phase}")
            # Tell whoever is watching the idle server that this mirror is finished, so
            # their stream closes and `EventSource` reconnects onto the new one. Without
            # this, the browser that pressed the button sits on a mirror nothing will
            # ever be pushed to and shows a start screen all evening.
            self._mirror.ended()
            self._mirror = Mirror()
            self._floor = None if watch_only else Floor()
            self._phase = STARTING
            self._campaign = slug
            self._error = ""
            mirror, floor = self._mirror, self._floor
            self._thread = threading.Thread(
                target=self._evening, args=(slug, mirror, floor), daemon=True
            )
            self._thread.start()
        return Started(True)

    def end(self) -> Started:
        """Ask the running evening to stop, the way a person at the table would.

        `/quit` on the floor rather than a flag the loop checks, because that is already
        how an evening ends and a second way to end one would be a second way for the
        between-session jobs to be skipped. A `watch_only` evening has no floor and
        therefore nothing to say this to — which is the honest answer, not a bug.
        """
        with self._lock:
            if self._phase != PLAYING or self._floor is None:
                return Started(False, "nothing is playing")
            floor = self._floor
        floor.typed("/quit")
        return Started(True)

    def wait(self, timeout: float) -> bool:
        """Block until the running evening has finished, or the timeout runs out.

        Exists for one caller and one moment: a container being stopped. `end` only puts
        `/quit` on the floor, and the between-session jobs — the sweep, the chronicle,
        the save — run on the evening's own thread afterwards. Returning immediately from
        `end` and then killing the process would lose exactly the work that makes an
        evening worth having played.
        """
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    # --- the thread --------------------------------------------------------

    def _evening(self, slug: str, mirror: Mirror, floor: Floor | None) -> None:
        """Build it, run it, and put the server back where it started.

        Every exit goes through `_idle`, including a failed build: a server that got
        stuck saying "starting" because a campaign would not load is a server nobody can
        use again without restarting it, which is the thing this whole task is about.
        """
        args = copy.copy(self._args)
        args.campaign = slug
        try:
            evening = self._build(self._cfg, args, self._herald)
        except SetupError as exc:
            mirror.note(exc.markup)
            mirror.ended()
            self._idle(error=str(exc))
            return
        except Exception as exc:  # a seat that fell over, a disk that filled
            mirror.note(f"[red]could not start:[/red] {type(exc).__name__}: {exc}")
            mirror.ended()
            self._idle(error=f"{type(exc).__name__}: {exc}")
            return

        with self._lock:
            self._phase = PLAYING
        table = self._table_for(evening, mirror, floor)
        keyboard = self._keyboard_for(evening, floor) if self._keyboard_for else None
        error = ""
        try:
            error = self._run(
                evening,
                table,
                floor=floor,
                herald=self._herald,
                commands=self._commands(evening) if self._commands else None,
                keyboard=keyboard,
                sweep=not self._args.no_sweep,
                chronicle=not self._args.no_chronicle,
            ).error
        except Exception as exc:  # pragma: no cover - the loop's own last resort
            mirror.note(f"[red]the evening stopped:[/red] {type(exc).__name__}: {exc}")
            error = f"{type(exc).__name__}: {exc}"
        finally:
            mirror.ended()
            self._idle(error=error)

    def _idle(self, error: str = "") -> None:
        """Back to a start screen, on a mirror nobody has been told is finished.

        The finished mirror stays in the watchers' hands until they reconnect; the new
        one is what they land on. Reusing the ended one would answer every reconnect with
        "this evening is over" forever, which is a poll loop wearing a screen.
        """
        with self._lock:
            self._mirror = Mirror()
            self._floor = None
            self._phase = IDLE
            self._campaign = ""
            self._error = error


class Held:
    """One evening, already running, owned by somebody else.

    `dndc play --serve` still works the way it always has: the evening owns the process,
    the CLI's own thread runs the loop, and the server is a thing it is also doing. That
    posture is right for a laptop on the table and this class is how it keeps it — the
    app talks to the same small interface either way, so there is one set of routes and
    not two.

    It cannot start an evening, because there is already one and something else owns it.
    It *can* end one, because `/quit` from a device is how P6.4 already ended a served
    session and taking that away to make a point would be a worse table.
    """

    def __init__(self, mirror: Mirror, floor: Floor | None = None) -> None:
        self._mirror = mirror
        self._floor = floor

    @property
    def mirror(self) -> Mirror:
        return self._mirror

    @property
    def floor(self) -> Floor | None:
        return self._floor

    @property
    def can_manage(self) -> bool:
        """No start or end routes, because there is nothing here to start or end.

        This evening was started by a command and ends when somebody says `/quit`, which
        is a turn and goes down the route that already exists. Building a session route
        that could only ever refuse would put a POST on a spectator link for no gain —
        and "read-only in the strong sense" is a claim `test_mirror` makes and should
        keep being able to make.
        """
        return False

    @property
    def can_play(self) -> bool:
        """A spectator server never had a floor and never builds a write route.

        This is the whole of P6.3's "protection by absence" and it survives P6.7b-iii
        untouched: `dndc play --serve --watch-only` still serves an app on which `POST
        /api/turn` does not exist, so the answer is 404 rather than a refusal that
        confirms there is something to be refused from.
        """
        return self._floor is not None

    @property
    def phase(self) -> str:
        return IDLE if self._mirror.over else PLAYING

    def state(self) -> dict:
        return {"phase": self.phase, "campaign": "", "error": ""}

    def campaigns(self) -> list[dict]:
        """Nothing to offer: this server cannot start an evening, so a list of things it
        could start would be a menu with no kitchen behind it."""
        return []

    def start(self, campaign: str, *, watch_only: bool = False) -> Started:
        return Started(False, "this server was started with its evening already running")

    def end(self) -> Started:
        """Kept for the interface, and reachable from the CLI rather than from a route:
        `_cmd_serve` calls it on Ctrl+C so an evening writes its save before the process
        goes. A browser ends this evening the way it always has, by saying `/quit`."""
        if self._floor is None or self._mirror.over:
            return Started(False, "nothing is playing")
        self._floor.typed("/quit")
        return Started(True)
