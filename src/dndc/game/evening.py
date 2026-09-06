"""Running an evening once it has been built (P6.7b-iii).

`game/setup.py` builds one; this runs it. They are separate for the same reason the
build was separated from the CLI: a browser that can start an evening has to be able to
reach both halves, and until this file existed the second half was a `while True:` in
the middle of `_cmd_play` that only a terminal could get to.

**The requirement here is narrower than "no console", and getting that right is what
kept this small.** A hosted evening is allowed to *write* — `rich` on a container's
stdout is the log, and losing the narration out of `docker logs` would be a loss, not a
win. What it may never do is *read*: nothing in a hosted evening may block on stdin,
because there is nobody there and the block would be forever. So the `Table` keeps its
own console and this module keeps a `Herald`, and the only stdin in the building is the
keyboard thread the CLI starts — which a hosted evening simply does not start.

The loop itself is unchanged from the one P6.4 shipped, down to the ordering of the
between-session jobs, which is load-bearing and commented where it matters.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable

from dndc.game.floor import WEB, Floor
from dndc.game.session import PlaySession, SessionError
from dndc.game.setup import Evening, Herald, QuietHerald
from dndc.gm import SCAFFOLDING_TEMPLATES

#: How often the loop looks up from the queue when a floor is in play. Short enough that a
#: terminal going away is noticed promptly, long enough to cost nothing while an evening
#: sits waiting for somebody to decide what their character does.
FLOOR_POLL = 0.25

#: Rendered into every message that has to name the levels, so they cannot drift apart.
SCAFFOLDING_CHOICES = " | ".join(sorted(SCAFFOLDING_TEMPLATES))

#: How often the CLI reminds players that `/scaffolding` exists, in player turns.
#: D-006 as amended puts the fade in the players' hands, which only works if they know
#: the handle is there — and OD-11 puts meta in the chrome, so the GM cannot mention it.
SCAFFOLDING_HINT_EVERY = 12


def should_hint_scaffolding(player_turns: int, scaffolding: str) -> bool:
    """Whether the chrome should mention `/scaffolding` after this turn.

    Only a periodic nudge, and only while there is something left to turn down — at
    `off` the command has nothing to offer and the reminder is just noise.
    """
    if scaffolding == "off" or player_turns <= 0:
        return False
    return player_turns % SCAFFOLDING_HINT_EVERY == 0


@dataclass(frozen=True)
class Closed:
    """How an evening ended, for a caller that has to say so.

    `opened` is false only when the opening narration itself failed — the one exit that
    skips the between-session jobs, because there is no session's worth of anything to
    sweep or chronicle. The CLI turns that into exit code 1; a server turns it into a
    line on the page.
    """

    opened: bool
    error: str = ""


def run_evening(
    evening: Evening,
    table,
    *,
    floor: Floor | None = None,
    herald: Herald | None = None,
    commands: Callable[[str], object] | None = None,
    keyboard=None,
    sweep: bool = True,
    chronicle: bool = True,
) -> Closed:
    """Open the scene, take lines until somebody stops, then run the closing jobs.

    `floor=None` is the hot seat and the only mode that reads stdin here. Everything
    else — a served evening at the table, a hosted one with no terminal at all — takes
    every line off the floor, and the loop cannot tell a keyboard from a browser. That
    was P6.4's whole point and it is what makes a hosted evening the same evening.

    `commands` handles a line beginning with `/`. It is a callable rather than an import
    because the slash commands are a *front end's* vocabulary — they print sheets and
    inventories to whoever is running the program — and the loop's only interest is
    whether one of them said to stop or to hand the seat over.

    `keyboard` is the thread feeding the floor from a terminal, when there is one. The
    loop watches it only to say something useful when it dies: a served evening does not
    end because the terminal did, and a hosted one never had a terminal to lose.
    """
    herald = herald or QuietHerald()
    session: PlaySession = evening.session

    try:
        try:
            session.open_scene(table)
        except SessionError as exc:
            herald.say(f"\n[red]error:[/red] {exc}")
            return Closed(opened=False, error=str(exc))

        orphaned = False
        while True:
            if floor is None:
                member = session.member
                raw = herald.ask(f"[bold cyan]{member.player} ({member.name})[/bold cyan]")
                if raw is None:
                    herald.say("\n[dim]session ended[/dim]")
                    break
                text = raw.strip()
            else:
                # Every line arrives the same way whoever typed it, and the loop cannot
                # tell a keyboard from a browser — which is the point. The wait is bounded
                # so a terminal that has gone away (EOF, ^D) is noticed rather than
                # blocking the process forever on a queue nobody will ever add to.
                line = floor.next(timeout=FLOOR_POLL)
                if line is None:
                    if keyboard is not None and not keyboard.is_alive() and not orphaned:
                        # The keyboard has gone (EOF, ^D) but the sofa has not. A served
                        # session does not end because the terminal did — that is most of
                        # the point of serving it, and a hosted one (P6.7) never has a
                        # terminal to lose. `/quit` from either side still ends it, and
                        # Ctrl+C still ends the process.
                        orphaned = True
                        herald.say(
                            "\n[dim]terminal closed — still serving. /quit from a device, "
                            "or Ctrl+C here[/dim]"
                        )
                    continue
                text = line.text.strip()
                if line.source == WEB:
                    herald.say(
                        f"\n[cyan]{line.character}[/cyan] [dim](from the couch)[/dim]: {text}"
                    )

            if not text:
                continue
            if text.startswith("/"):
                if commands is None:
                    # A front end with no command vocabulary. Saying so beats swallowing
                    # the line, which would look to the sofa like the table ignored them.
                    table.notice(f"[yellow]no commands here[/yellow] [dim]— {text}[/dim]")
                    continue
                outcome = commands(text)
                if outcome.quit:
                    break
                if outcome.active:
                    session.hand_to(outcome.active)
                table.changed()
                continue

            herald.say("")
            with (floor.taking_a_turn() if floor else nullcontext()):
                played = session.take_turn(text, table)
            if played is None:
                # A failed turn is not a turn: it gets no trailing spacing and no
                # scaffolding hint, because nothing was narrated to react to.
                continue
            if should_hint_scaffolding(session.player_turns, evening.engine.builder.scaffolding):
                herald.say(
                    f"\n[dim]— GM offering you options more than you want? "
                    f"/scaffolding {SCAFFOLDING_CHOICES}[/dim]"
                )
            herald.say("")
    finally:
        session.close()

    # The between-session jobs run *before* the sofa is told the evening is over, because
    # the sweep asks the table a question and P6.5 lets a device answer it. Tearing the
    # server down first pushed that question to a mirror nobody could reach and then took
    # silence for a decline — found live, not in a test, because every test that could
    # have caught it owned the mirror directly and never had a socket to lose.
    session.finish(table, sweep=sweep, chronicle=chronicle)
    return Closed(opened=True)
