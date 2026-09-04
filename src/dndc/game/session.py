"""One turn loop, two front ends (P6.1).

Phase 6 puts a browser in front of the same campaign the CLI plays. The tempting way to
do that is to write a second loop in the web layer — and it is the wrong way for the same
reason a save point holds nothing the ledger owns (P5.1): two authorities for one
behaviour drift the first time one path is changed and the other is not. Here the drift
would be silent and expensive. The web loop would forget to record a save, or to confirm
an item, or to close the session, and the campaign it produced would be subtly not the
campaign the CLI produces — in a project whose entire purpose is measuring whether a
campaign stays consistent with itself.

So there is one loop, and it lives here. `_cmd_play` was doing four separable jobs at
once: building a session, running turns, asking the table things, and drawing on a
terminal. The first two are this module. The last two are the `Table` a caller passes
in — `rich` today, a browser in P6.3 onward.

**The protocol is deliberately about questions and answers, not about widgets.** Nothing
here knows what a panel looks like; it knows that after a turn somebody must be shown
what happened, and that before an item reaches a sheet somebody must say yes. Those are
the facts that are true at a table regardless of what the table is looking at, and they
are the ones a second front end must not be free to skip.

**What is still in the CLI, and why.** The end-of-session jobs reach the table through
`Table.sweep` and `Table.chronicle` rather than being run here, because both are
confirmation flows built out of `rich` prompts, and untangling those is P6.5's whole
task. The *ordering* is here, where it belongs: sweep, then chronicle, then close the
save, then say what it cost. That sequence encodes a decision (an interrupted end-of-
session should lose the summary rather than the canon) and a front end must not be able
to get it wrong by writing its own.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from dndc.game.saves import Resume, SaveStore, restore
from dndc.game.turn import TurnEngine, TurnResult
from dndc.gm.context import CampaignContext, GMPromptBuilder
from dndc.logging import SessionLog
from dndc.models.base import GMBackend, GMBackendError
from dndc.schema.sheet import CharacterSheet

#: Ceiling for a randomly drawn session seed. Same value the CLI has always used; it
#: lives here now because the seed is part of a session, not part of an argument parser.
MAX_SEED = 2**32


class SessionError(RuntimeError):
    """A session could not be started, or could not continue.

    Raised rather than printed: this module has no terminal, and a caller that wants to
    show a red line can catch it. That is the whole difference between a loop and a CLI.
    """


@runtime_checkable
class Narration(Protocol):
    """One GM reply, arriving in pieces.

    `feed` takes streamed text, `dialogue` takes a character's line once a local seat has
    finished speaking it, and `finish` says the reply is over. A terminal writes them out
    as they come; a browser pushes them down an event stream. Neither is this module's
    business.
    """

    def feed(self, chunk: str) -> None: ...

    def dialogue(self, reply) -> None: ...

    def finish(self) -> None: ...


@runtime_checkable
class Table(Protocol):
    """Whoever is on the other side of the loop.

    Every method is something that has to happen at a real table: somebody is told what
    the GM said, somebody says yes before an item lands on a sheet, somebody is told what
    the evening cost. A front end may render any of it however it likes and may not
    decline to be asked.
    """

    def notice(self, text: str) -> None: ...

    def error(self, text: str) -> None: ...

    def narration(self) -> Narration: ...

    def opened(self, result: TurnResult) -> None: ...

    def played(self, result: TurnResult) -> None: ...

    def inventory(self, tags, acting: str, turn: int) -> int: ...

    def changed(self) -> None: ...

    def sweep(self, session: PlaySession) -> None: ...

    def chronicle(self, session: PlaySession) -> None: ...


@dataclass
class PlaySession:
    """A campaign, mid-evening: everything a turn needs and nothing about a screen."""

    campaign: CampaignContext
    engine: TurnEngine
    log: SessionLog
    backend: GMBackend
    sheets: dict[str, CharacterSheet]
    items: object
    acting: str
    billing: str
    seed: int
    saves: SaveStore | None = None
    resume: Resume | None = None
    #: Closed when the session ends. The NPC tier holds its own connections.
    closers: list = field(default_factory=list)
    #: Turns the *players* have taken this run. Not `len(history)`, which includes the
    #: opening scene and anything a resumed save restored.
    player_turns: int = 0

    # --- building ----------------------------------------------------------

    @classmethod
    def start(
        cls,
        campaign: CampaignContext,
        sheets: dict[str, CharacterSheet],
        *,
        backend: GMBackend,
        log: SessionLog,
        engine: TurnEngine,
        items,
        acting: str,
        billing: str,
        seed: int,
        saves: SaveStore | None = None,
        resume: Resume | None = None,
        closers=(),
    ) -> PlaySession:
        """Assemble a session from parts a caller has already built.

        Everything here is passed in rather than constructed, because *which* backend,
        seat, and log a session runs on is a front end's decision — the CLI reads flags,
        a server will read a form — while what happens once it has them is not.
        """
        if not campaign.party:
            raise SessionError("no characters loaded")
        return cls(
            campaign=campaign,
            engine=engine,
            log=log,
            backend=backend,
            sheets=sheets,
            items=items,
            acting=acting,
            billing=billing,
            seed=seed,
            saves=saves,
            resume=resume,
            closers=list(closers),
        )

    # --- who is playing ----------------------------------------------------

    @property
    def member(self):
        """The party member whose seat it currently is."""
        return self.sheets_by_name[self.acting.lower()]

    @property
    def sheets_by_name(self) -> dict[str, object]:
        return {member.name.lower(): member for member in self.campaign.party}

    @property
    def sheet(self) -> CharacterSheet | None:
        """The acting character's full sheet, which a check resolves against."""
        return self.sheets.get(self.acting.lower())

    def hand_to(self, name: str) -> None:
        self.acting = name

    # --- the loop ----------------------------------------------------------

    def open_scene(self, table: Table) -> TurnResult | None:
        """The GM speaks first, as at a table.

        Skipped when the campaign already has history — a resumed session walks back into
        a scene that is already running, and opening it again would narrate the party
        arriving somewhere they have been standing for an hour.
        """
        if self.campaign.history:
            return None

        narration = table.narration()
        try:
            opened = self.engine.open_scene(
                on_text=narration.feed, on_dialogue=narration.dialogue
            )
        except GMBackendError as exc:
            raise SessionError(str(exc)) from exc
        except Exception as exc:  # network, rate limit, a host that went away
            raise SessionError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            narration.finish()

        # The opening scene should not be handing out gear — the prompt says as much —
        # but a proposal silently dropped here would be a hole, and holes are what the
        # confirmation step exists to close.
        table.inventory(opened.inventory, self.acting, len(self.campaign.history))
        table.opened(opened)
        self.record()
        return opened

    def take_turn(self, text: str, table: Table) -> TurnResult | None:
        """One player line, through the GM, onto the sheets, into the save.

        Returns None when the turn failed. Before P5.1 a dropped connection ended the
        process and the evening with it; the save point made that recoverable, but
        recovering from a traceback is still a worse table than being told to say it
        again. The turn is not lost silently — the engine has already logged a `pending`
        row with no terminal, which is exactly what a failed call should look like.
        """
        self.player_turns += 1
        narration = table.narration()
        try:
            result = self.engine.run(
                text,
                player=self.member.player,
                sheet=self.sheet,
                on_text=narration.feed,
                # Delivered as each character answers rather than collected and dumped at
                # the end: an NPC line takes seconds on a local seat, and a table watching
                # nothing happen is a table that thinks it has hung.
                on_dialogue=narration.dialogue,
            )
        except Exception as exc:
            narration.finish()
            table.error(f"that turn failed: {type(exc).__name__}: {exc}")
            return None
        narration.finish()

        table.played(result)
        table.inventory(result.inventory, self.acting, len(self.campaign.history))
        # Written before the next line rather than at session end: the point of a save
        # point is that an evening does not end, it stops.
        self.record()
        return result

    def record(self) -> None:
        """Write the save point, if this session has one."""
        if self.saves is not None:
            self.saves.record(self.campaign, acting=self.acting, log=self.log)

    # --- ending ------------------------------------------------------------

    def finish(self, table: Table, sweep: bool = True, chronicle: bool = True) -> None:
        """The between-session jobs, in the order an interruption should find them.

        The chronicle runs *after* the sweep deliberately. The two are independent, but
        the sweep is the cheap confirmable one and the canon ledger is the instrument this
        project measures drift with — so an end-of-session that gets cut short loses the
        summary, which regenerates for free, rather than the facts, which do not.
        """
        if self.campaign.history:
            if sweep:
                table.sweep(self)
            if chronicle:
                table.chronicle(self)

        if self.saves is not None:
            # Closing is what tells the next run this was a bedtime and not a crash: the
            # scene survives, the turn window does not, and the chronicle just written is
            # what carries this session into the next one (D-002).
            self.saves.close(self.campaign, acting=self.acting, log=self.log)

    def close(self) -> None:
        """Release the seats. Safe to call twice; a front end may not skip it."""
        self.backend.close()
        for closer in self.closers:
            closer.close()
        self.closers = []


def resume_from(saves: SaveStore, campaign: CampaignContext, scene: str = "") -> Resume | None:
    """Load and apply a save, if there is one. `scene` overrides what it remembered.

    An explicit scene is somebody deliberately moving the party; it beats whatever the
    save says about where they were standing.
    """
    save = saves.load()
    if save is None:
        return None
    resume = restore(save, campaign)
    if scene:
        campaign.scene = scene
    return resume


def acting_member(campaign: CampaignContext, resume: Resume | None) -> str:
    """Whose seat it is. A resumed save names them; otherwise the party's first member.

    Checked against the party rather than trusted: a save can outlive the character it
    names (a sheet renamed, a player retiring somebody), and handing the prompt to a
    character who is not in the room would end the session before it started.
    """
    if resume is not None and resume.acting:
        for member in campaign.party:
            if member.name.casefold() == resume.acting.casefold():
                return member.name
    return campaign.party[0].name


def draw_seed(requested: int | None = None) -> int:
    return requested if requested is not None else random.randrange(MAX_SEED)


def build_engine(
    campaign: CampaignContext,
    backend: GMBackend,
    *,
    log: SessionLog,
    scaffolding: str,
    seed: int,
    max_tokens: int,
    billing: str,
    prices: dict,
    canon,
    voice=None,
    stance=None,
) -> TurnEngine:
    """The engine a session runs on. One place, so both front ends get the same one."""
    return TurnEngine(
        backend=backend,
        campaign=campaign,
        builder=GMPromptBuilder(scaffolding=scaffolding),
        rng=random.Random(seed),
        log=log,
        max_tokens=max_tokens,
        billing=billing,
        prices=prices,
        canon=canon,
        voice=voice,
        stance=stance,
    )
