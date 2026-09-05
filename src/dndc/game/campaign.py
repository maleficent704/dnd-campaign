"""Creating and locating campaigns on disk."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dndc.config import (
    CAMPAIGNS_DIR_ENV,
    DEFAULT_CAMPAIGNS_DIR,
    DEFAULT_CONFIG_PATH,
    load_config,
)
from dndc.schema.campaign import CAMPAIGN_FILE, Campaign, slugify

CAMPAIGNS_DIRNAME = "campaigns"
CHARACTERS_DIRNAME = "characters"
SAVES_DIRNAME = "saves"


class CampaignError(RuntimeError):
    """Raised when a campaign cannot be created or found."""


def resolve_campaigns_root(configured: str, root: Path | None = None) -> Path:
    """Resolve a configured campaigns directory against the repo root unless absolute.

    The same rule `resolve_log_dir` uses for `logging.dir`: a relative path stays
    relative to the checkout, so `campaigns/` keeps meaning what it has always meant no
    matter where `dndc` is invoked from, and an absolute path is taken as given.
    """
    candidate = Path(os.path.expanduser(configured))
    if candidate.is_absolute():
        return candidate
    return (root or Path(__file__).resolve().parents[3]) / candidate


def configured_campaigns_dir() -> str:
    """The configured directory, before it becomes a path.

    Precedence: `DNDC_CAMPAIGNS_DIR` > config.yaml `campaigns.dir` > `campaigns/`.
    The environment wins because that is the lever a container has — the config in the
    image is the wrong place to say where the volume is mounted — and because it matches
    `load_env_file`, where a real environment variable always beats a file.

    Read here rather than threaded down from the CLI. `campaign_dir()` is reached from
    about twenty call sites that pass no `root`, and one that forgot to thread it would
    not fail: it would read an empty directory inside the image, find no campaign, and
    offer to create one. Losing a campaign while reporting success is the same failure
    shape P6.6 found in the bind address, and it takes the same fix — a single
    resolution point with nothing to bypass.

    A missing config.yaml falls back to the default; an *invalid* one is allowed to
    raise, because that is a real error and a silent fallback would point the table's
    saves somewhere they were never meant to go.
    """
    override = os.environ.get(CAMPAIGNS_DIR_ENV, "").strip()
    if override:
        return override
    if not DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CAMPAIGNS_DIR
    return load_config(DEFAULT_CONFIG_PATH).campaigns.dir


def default_campaigns_root() -> Path:
    return resolve_campaigns_root(configured_campaigns_dir())


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
