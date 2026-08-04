"""Creating and locating campaigns on disk."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from dndc.schema.campaign import CAMPAIGN_FILE, Campaign, slugify

CAMPAIGNS_DIRNAME = "campaigns"
CHARACTERS_DIRNAME = "characters"
SAVES_DIRNAME = "saves"


class CampaignError(RuntimeError):
    """Raised when a campaign cannot be created or found."""


def default_campaigns_root() -> Path:
    return Path(__file__).resolve().parents[3] / CAMPAIGNS_DIRNAME


def campaign_dir(slug: str, root: Path | None = None) -> Path:
    return (root or default_campaigns_root()) / slug


def create_campaign(
    name: str,
    root: Path | None = None,
    players: list[str] | None = None,
    scaffolding: str = "high",
    play_mode: str = "hotseat",
    created: date | None = None,
) -> Campaign:
    """Lay out `campaigns/<slug>/` and write its definition.

    Refuses to touch an existing campaign directory. Overwriting one would destroy
    character sheets and, from Phase 2, the canon ledger — never something to do as a
    side effect of a mistyped name.
    """
    slug = slugify(name)
    target = campaign_dir(slug, root)
    if target.exists():
        raise CampaignError(
            f"campaign {slug!r} already exists at {target} — refusing to overwrite"
        )

    campaign = Campaign(
        name=name.strip(),
        slug=slug,
        created=created or date.today(),
        scaffolding=scaffolding,
        play_mode=play_mode,
        players=players or [],
    )

    (target / CHARACTERS_DIRNAME).mkdir(parents=True)
    (target / SAVES_DIRNAME).mkdir(parents=True)
    campaign.save(target / CAMPAIGN_FILE)
    # saves/ is gitignored, so without this the directory vanishes on clone.
    (target / SAVES_DIRNAME / ".gitkeep").write_text("", encoding="utf-8")
    return campaign


def load_campaign(slug: str, root: Path | None = None) -> Campaign:
    path = campaign_dir(slug, root) / CAMPAIGN_FILE
    if not path.exists():
        raise CampaignError(f"no campaign at {path}")
    return Campaign.load(path)


def list_campaigns(root: Path | None = None) -> list[Campaign]:
    base = root or default_campaigns_root()
    if not base.exists():
        return []
    found = []
    for entry in sorted(base.iterdir()):
        definition = entry / CAMPAIGN_FILE
        if definition.exists():
            found.append(Campaign.load(definition))
    return found
