"""The save point — where the party is standing, and nothing else (P5.1).

Everything durable about a campaign already has a file and a writer: canon in
`canon.yaml`, the sheets in `characters/`, the campaign's own backgrounds in
`backgrounds.yaml`, past sessions in `chronicle.yaml`. What none of them holds is the
part a table would call *where we got to* — the scene as the GM last described it, the
turns still inside the prompt window, and whose seat it is.

So this file stores exactly that, and deliberately stores no canon, no sheets and no
chronicle. Copying any of them here would create a second authority for the same fact,
and two authorities drift the first time one path writes and the other does not.

The save also carries the session's lineage — id, log, `seq` — which is what turns the
npc-village `seq` rider from a mechanism into a thing that actually happens: a session
picked up after a crash reopens its own log and the counter continues, instead of the
evening arriving in the record as two unrelated halves.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dndc.schema.events import utcnow

#: `campaigns/<slug>/saves/state.yaml`. One campaign, one place it got to.
SAVE_FILE = "state.yaml"
#: Bumped when the shape changes incompatibly. A save from the future is refused rather
#: than half-read: a partly-restored scene is worse than an honestly missing one.
SAVE_VERSION = 1


class SavedLine(BaseModel):
    """One NPC line, kept beside the turn it followed rather than inside the narration."""

    model_config = ConfigDict(extra="forbid")

    speaker: str
    text: str


class SavedTurn(BaseModel):
    """One completed exchange, in the shape `CampaignContext.window()` rebuilds from."""

    model_config = ConfigDict(extra="forbid")

    player_input: str
    narration: str
    speaker: str = "The party"
    opening: bool = False
    dialogue: list[SavedLine] = Field(default_factory=list)


class SavePoint(BaseModel):
    """A campaign's play state between turns.

    `closed` is the whole of the difference between a crash and a bedtime. An open save
    is a session that stopped mid-evening: its window is still the session's own recent
    memory and comes back whole. A closed save is a session that ended properly — the
    sweep and the chronicle have run — and its turns are **not** restored, because
    D-002 says a past session reaches the prompt as chronicle prose and not as raw
    transcript. Replaying last week's turns on top of the chronicle that summarises them
    is the growing-transcript failure the three-layer memory exists to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = SAVE_VERSION
    campaign: str = Field(min_length=1)
    saved_at: datetime = Field(default_factory=utcnow)
    #: The GM's standing description of where the party is. Survives a closed save: it is
    #: the one thing a new evening genuinely needs and the chronicle does not carry.
    scene: str = ""
    #: Whose seat it is, by character name (hot-seat, OD-4).
    acting: str | None = None
    turns: list[SavedTurn] = Field(default_factory=list)
    #: How many turns that session played. Kept when `closed` empties `turns`, because
    #: `session_meta.resumed_turns` still has to be able to say so.
    turns_played: int = 0
    closed: bool = False
    #: Session lineage — what the next run resumes into, or records having come from.
    session_id: str | None = None
    log: str | None = None
    seq: int | None = None

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(mode="json"), sort_keys=False, allow_unicode=True
        )

    @classmethod
    def from_yaml(cls, text: str) -> Self:
        return cls.model_validate(yaml.safe_load(text) or {})

    @classmethod
    def load(cls, path: Path | str) -> Self | None:
        """Read a save point, or `None` if there is not one to read.

        A missing file is not an error — the first session of every campaign has none.
        """
        target = Path(path)
        if not target.exists():
            return None
        return cls.from_yaml(target.read_text(encoding="utf-8"))

    def save(self, path: Path | str) -> Path:
        """Rewrite the save point atomically.

        The same discipline as a character sheet: a crash during the write of turn 40
        must not take the session with it. This is the one file in the project that is
        rewritten rather than appended to, which is why it holds nothing the append-only
        log is the record of.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(self.to_yaml(), encoding="utf-8")
        os.replace(temp, target)
        return target
