"""Campaign definition — the durable, hand-editable description of a campaign.

Campaign *content* is data (CLAUDE.md): this file describes the campaign, not the story
inside it. Play state (canon ledger, chronicle, save points) lands in Phase 2 and lives
under `campaigns/<slug>/saves/`, which is gitignored.

Kept deliberately small. Phase 1 and 2 will extend it; guessing at fields now would just
mean writing them twice.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field

CAMPAIGN_FILE = "campaign.yaml"


def slugify(name: str) -> str:
    """Filesystem-safe directory name.

    Windows reserved device names (nul, con, aux, prn, com1-9, lpt1-9) are suffixed
    rather than rejected — a campaign called "Aux" is a reasonable thing to want, and a
    directory called `aux` is not creatable on this household's primary box.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().casefold()).strip("-")
    if not slug:
        raise ValueError(f"campaign name {name!r} has no usable characters")
    if re.fullmatch(r"nul|con|aux|prn|com[1-9]|lpt[1-9]", slug):
        slug = f"{slug}-campaign"
    return slug


class Campaign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    created: date
    #: D-006 — how hard the GM leans on surfacing options. Fades as players find their feet.
    scaffolding: str = "high"
    #: OD-4 — hot-seat until the Phase 6 GUI.
    play_mode: str = "hotseat"
    srd_edition: str = "SRD 5.1 (2014)"
    players: list[str] = Field(default_factory=list)
    premise: str = ""
    notes: str = ""

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(mode="json"), sort_keys=False, allow_unicode=True
        )

    @classmethod
    def from_yaml(cls, text: str) -> Self:
        return cls.model_validate(yaml.safe_load(text))

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.from_yaml(Path(path).read_text(encoding="utf-8"))
