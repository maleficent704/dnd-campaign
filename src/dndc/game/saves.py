"""Reading and writing a campaign's save point, and deciding how to pick it up (P5.1).

The store is deliberately dumb: it knows where the file lives, what goes in it, and
nothing about the turn loop. What is *not* dumb is `restore`, which makes the one design
call in the task — whether the turns in a save come back — and it is the difference
between a crash and a bedtime. See `SavePoint`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dndc.game.campaign import SAVES_DIRNAME, campaign_dir
from dndc.gm.context import CampaignContext, SpokenLine, Turn
from dndc.logging import SessionLog
from dndc.schema.save import SAVE_FILE, SAVE_VERSION, SavedLine, SavedTurn, SavePoint


class SaveError(RuntimeError):
    """Raised when a save point cannot be used."""


class SaveStore:
    """The save point for one campaign."""

    def __init__(self, path: Path | str, slug: str) -> None:
        self.path = Path(path)
        self.slug = slug

    @classmethod
    def for_campaign(cls, slug: str, root: Path | None = None) -> SaveStore:
        return cls(campaign_dir(slug, root) / SAVES_DIRNAME / SAVE_FILE, slug)

    def load(self) -> SavePoint | None:
        """The save point on disk, or `None`. Refuses one written by a newer version."""
        save = SavePoint.load(self.path)
        if save is None:
            return None
        if save.version > SAVE_VERSION:
            raise SaveError(
                f"{self.path} was written by a newer version of dndc "
                f"(save v{save.version}, this build reads v{SAVE_VERSION})"
            )
        return save

    def record(
        self,
        campaign: CampaignContext,
        acting: str | None = None,
        log: SessionLog | None = None,
        closed: bool = False,
    ) -> SavePoint:
        """Write where the campaign got to. Called after every turn."""
        save = SavePoint(
            campaign=self.slug,
            scene=campaign.scene,
            acting=acting,
            turns=[] if closed else [_saved(turn) for turn in campaign.history],
            turns_played=len(campaign.history),
            closed=closed,
            session_id=log.session_id if log is not None else None,
            log=str(log.path) if log is not None else None,
            seq=log.seq if log is not None else None,
        )
        save.save(self.path)
        return save

    def close(
        self,
        campaign: CampaignContext,
        acting: str | None = None,
        log: SessionLog | None = None,
    ) -> SavePoint:
        """Mark the evening finished. The scene stays; the turn window does not."""
        return self.record(campaign, acting=acting, log=log, closed=True)


@dataclass(frozen=True)
class Resume:
    """What a save point tells the next run to do."""

    save: SavePoint
    #: Turns put back into the prompt window. Zero for a closed save, by design.
    turns: int
    #: True when the run continues the save's own session: same log file, same
    #: `session_id`, `seq` carrying on from where it stopped.
    continuing: bool
    log_path: Path | None = None

    @property
    def session_id(self) -> str | None:
        return self.save.session_id

    @property
    def acting(self) -> str | None:
        return self.save.acting

    @property
    def played(self) -> int:
        return self.save.turns_played


def restore(save: SavePoint, campaign: CampaignContext) -> Resume:
    """Put a save point back into a campaign context, and say how to open the log.

    The scene always comes back — it is the one thing a new evening needs that the
    chronicle does not carry, since the chronicle summarises what *happened* and not
    where everyone is standing when it stopped.

    The turns come back only from an **open** save. A closed save's session has already
    been swept and chronicled, and D-002 is explicit that a past session reaches the
    prompt as chronicle prose; restoring its raw turns on top of the summary of those
    same turns is the growing-transcript failure the three memory layers exist to
    prevent. It also lets the GM open the new session properly, which is what the table
    would expect after a week away.
    """
    campaign.scene = save.scene or campaign.scene
    turns = 0
    if not save.closed:
        campaign.history = [_turn(saved) for saved in save.turns]
        turns = len(campaign.history)

    log_path = Path(save.log) if save.log else None
    # A resumable session needs its log still to be there: continuing `seq` into a file
    # that has been moved or cleaned away would restart the counter at zero and claim
    # otherwise. Losing the log costs the continuity, never the scene.
    continuing = bool(not save.closed and save.session_id and log_path and log_path.exists())
    return Resume(save=save, turns=turns, continuing=continuing, log_path=log_path)


def _saved(turn: Turn) -> SavedTurn:
    return SavedTurn(
        player_input=turn.player_input,
        narration=turn.narration,
        speaker=turn.speaker,
        opening=turn.opening,
        dialogue=[SavedLine(speaker=line.speaker, text=line.text) for line in turn.dialogue],
    )


def _turn(saved: SavedTurn) -> Turn:
    return Turn(
        player_input=saved.player_input,
        narration=saved.narration,
        speaker=saved.speaker,
        opening=saved.opening,
        dialogue=tuple(
            SpokenLine(speaker=line.speaker, text=line.text) for line in saved.dialogue
        ),
    )
