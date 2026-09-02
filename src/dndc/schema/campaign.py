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

from dndc.schema.srd import Background

CAMPAIGN_FILE = "campaign.yaml"
#: Original backgrounds, beside `canon.yaml` — campaign content, not ruleset (D-007).
BACKGROUNDS_FILE = "backgrounds.yaml"


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


class CampaignBackground(Background):
    """A background this table wrote, granted exactly as an SRD one is.

    Fable's 2026-08-15 (c) ruling: the SRD has one background (Acolyte) and the rest are
    PHB, so the *mechanism* was complete and the dataset was one row. Original backgrounds
    are the D-007-native answer — the mechanism (a name, two skills, a small extra,
    flavour) is uncopyrightable, and the names and text generated here are this campaign's
    own.

    A subclass of the SRD type rather than a parallel one, because everything downstream
    should be unable to tell the difference: `build_character` grants these by the same
    code path, and a character with an invented background is not a second-class sheet.

    Two fields the SRD type has no use for:

    - `languages` names what the background teaches. The SRD's `languages_choose` is a
      *choice* the character makes later; a background written for one character can
      simply say which language it taught, and a grant with nothing left to decide cannot
      be left half-spent.
    - `proposed_for` / `established` are provenance. The event log carries the same facts,
      but this file outlives any one session's log and is the artifact a human reads when
      deciding whether a second character may take this background.
    """

    #: Languages granted outright. At most one, per the ruling's "small extra".
    languages: tuple[str, ...] = ()
    #: The character whose interview produced it. It outlives them and is reusable.
    proposed_for: str | None = None
    established: date | None = None


class BackgroundBook(BaseModel):
    """`campaigns/<slug>/backgrounds.yaml` — the campaign's own backgrounds.

    Beside `canon.yaml` and for the same reason: what play establishes has to survive the
    process. A background is reusable by construction, so the second character to want a
    Salt-Road Grifter gets the same one rather than a near-miss with the same name.
    """

    model_config = ConfigDict(extra="forbid")

    backgrounds: list[CampaignBackground] = Field(default_factory=list)

    def __iter__(self):
        return iter(self.backgrounds)

    def __len__(self) -> int:
        return len(self.backgrounds)

    def names(self) -> list[str]:
        return [background.name for background in self.backgrounds]

    def get(self, name: str) -> CampaignBackground | None:
        """Case-insensitive lookup by name — what the GM writes is what it means."""
        if not name:
            return None
        folded = name.strip().casefold()
        for background in self.backgrounds:
            if background.name.casefold() == folded or background.index == folded:
                return background
        return None

    def add(self, background: CampaignBackground) -> CampaignBackground:
        """File a confirmed background. Re-adding an existing name is a no-op."""
        held = self.get(background.name)
        if held is not None:
            return held
        self.backgrounds.append(background)
        return background

    def to_yaml(self) -> str:
        payload = self.model_dump(mode="json", exclude_defaults=True)
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    @classmethod
    def load(cls, path: Path | str) -> Self:
        target = Path(path)
        if not target.exists():
            return cls()
        return cls.model_validate(yaml.safe_load(target.read_text(encoding="utf-8")) or {})

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target
