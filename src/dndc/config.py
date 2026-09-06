"""Typed loader for config.yaml.

Everything that names a model or an endpoint routes through here. Code must never
hardcode a model name or URL (CLAUDE.md, Model seats).
"""

from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_env_file(path: Path | str | None = None) -> list[str]:
    """Read `.env` into the process environment, returning the names it set.

    D-004 and `.env.example` both say the API key lives in a gitignored `.env`, and the
    "no ANTHROPIC_API_KEY" error tells you to put it there — but until this existed
    nothing read the file, so the only way to run the `api` adapter was to already have
    the key exported. Written by hand rather than pulling in `python-dotenv`: the format
    here is `KEY=value`, and that is a dozen lines.

    Resolved against the repo root, not the working directory, so it does not matter
    where `dndc` is invoked from. A real environment variable always wins — an explicitly
    exported key must not be silently replaced by a stale file.
    """
    resolved = Path(path) if path is not None else DEFAULT_ENV_PATH
    if not resolved.exists():
        return []

    loaded: list[str] = []
    for line in resolved.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):].lstrip()

        name, separator, value = stripped.partition("=")
        name = name.strip()
        if not separator or not name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded


class Billing(str, Enum):
    """Which GMBackend adapter fills the GM seat (D-004)."""

    API = "api"
    SUBSCRIPTION = "subscription"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BillingConfig(_Strict):
    default: Billing
    api_monthly_cap_note: str | None = None


class GMSeat(_Strict):
    backend: Literal["gmbackend"]
    model_default: str
    model_threshold: str


class OllamaSeat(_Strict):
    backend: Literal["ollama"]
    endpoint: str
    model: str


class Seats(_Strict):
    gm: GMSeat
    npc: OllamaSeat
    #: The jobs the table waits on — the P2.3 sweep, and anything interactive after it.
    #: Small and fast; its output is confirmation-gated, so recall beats precision.
    utility_interactive: OllamaSeat
    #: The jobs nobody watches — the P2.5 chronicle and its fold, future compression.
    #: Ungated and comprehension-critical, so quality beats latency (Fable, 2026-08-14).
    utility_batch: OllamaSeat

    @model_validator(mode="before")
    @classmethod
    def _reject_the_single_utility_seat(cls, value: object) -> object:
        """A pre-split config fails with instructions rather than a confusing schema error.

        Deliberately not migrated by mapping `utility` onto both seats. That would put the
        8B in the batch seat and silently undo the ruling this split exists to implement —
        the config would look upgraded and the chronicle would still be written by the
        model that inverted Brakewater.
        """
        if isinstance(value, dict) and "utility" in value:
            raise ValueError(
                "config.yaml has a single `utility:` seat; it was split on 2026-08-14. "
                "Replace it with `utility_interactive:` (the sweep — llama3.1:8b) and "
                "`utility_batch:` (the chronicle — llama3.3:70b)."
            )
        return value


class GameplayConfig(_Strict):
    scaffolding: Literal["high", "low", "off"]
    play_mode: Literal["hotseat", "web"]


#: `host: lan` — this machine's address on the LAN, found when the socket is bound rather
#: than written down. An address in a config file is a fact that goes stale on the next
#: DHCP lease, and a stale bind address does not fail loudly: it binds to nothing and the
#: server reports that it started.
LAN = "lan"
#: Every interface. **Not** a synonym for "the LAN" on this network — both kelly-pc and the
#: VM are Tailscale nodes, so a wildcard bind also serves the tailnet, including a phone on
#: cellular. See `docs/LAN-ACCESS.md` and race-control `operations/lan-only-services.md`.
EVERY_INTERFACE = "0.0.0.0"

DEFAULT_WEB_HOST = LAN
DEFAULT_WEB_PORT = 8765

#: The LAN gate's shared token (P6.7b, Kelly 2026-09-04). Environment only, never
#: config.yaml — that file is committed, and a token in it would be a committed secret.
#: Reaches a container through `env_file:`, the way `the-room` takes `ROOM_TOKEN`.
WEB_TOKEN_ENV = "DNDC_WEB_TOKEN"
#: Set by the deployment to say "this exposure is bigger than one evening on the LAN", so
#: that a missing token is a refusal to start rather than a service that comes up ungated.
WEB_REQUIRE_TOKEN_ENV = "DNDC_WEB_REQUIRE_TOKEN"

#: What to tell people the address is, when the process cannot work it out.
#: Inside a container, the socket is bound in a namespace of its own: the address
#: the server can see is `172.17.0.x`, which is true and useless, and the interface
#: it binds says nothing about what is actually published — that is the `ports:`
#: line in docker-compose.yml. P6.6's rule is that the startup line must tell the
#: truth about exposure, and a line that names an unreachable address while warning
#: about a tailnet it is not on breaks that rule in both directions (P6.7c).
WEB_PUBLIC_URL_ENV = "DNDC_WEB_PUBLIC_URL"
#: Short enough to guess is worse than absent: it reads as a control while being one.
MIN_WEB_TOKEN = 16


class WebConfig(_Strict):
    """Where the Phase 6 GUI listens (P6.6).

    Defaulted rather than required, so a config written before Phase 6 still loads — a
    table that never serves should not have to say so. The defaults are the safe pair,
    which is the point of moving them out of the code: P6.7 deploys this file, and the
    address a service binds to should be reviewable without reading Python.
    """

    host: str = DEFAULT_WEB_HOST
    port: int = Field(default=DEFAULT_WEB_PORT, ge=1, le=65535)

    @field_validator("host")
    @classmethod
    def _a_bind_address_not_a_url(cls, value: str) -> str:
        """Catch the two realistic typos here rather than at `bind()`.

        `http://192.168.50.160:8765` pasted out of a browser is the obvious one, and it
        fails deep inside uvicorn with an error about name resolution that says nothing
        about config.yaml.
        """
        host = value.strip()
        if not host:
            raise ValueError(f"web.host is empty — use `{LAN}`, an address, or {EVERY_INTERFACE}")
        if "://" in host or "/" in host:
            raise ValueError(f"web.host is a bind address, not a URL: {value!r}")
        return host


#: Where campaigns live when nothing says otherwise: beside the code, as they have since
#: P0.3. Relative paths resolve against the repo root, absolute ones are taken as given —
#: the same rule `logging.dir` already follows.
DEFAULT_CAMPAIGNS_DIR = "campaigns/"
#: The deployment's lever (P6.7). A container gets its data directory from `env_file:`,
#: not from a config baked into the image, so this wins over `campaigns.dir` — the same
#: precedence `load_env_file` uses, where a real environment variable always wins.
CAMPAIGNS_DIR_ENV = "DNDC_CAMPAIGNS_DIR"


class CampaignsConfig(_Strict):
    """Where campaign state is kept (P6.7a).

    Defaulted rather than required, so a config written before this key existed still
    loads and still points at the same directory it always did.

    This exists because a campaign is **data**: the canon ledger, the chronicle and the
    saves are what an evening produces, and they grow every session. Kelly's standing
    rule sends game saves to the NAS rather than into a code repo, and until now this
    project had no way to say where they go — the path was a `parents[3]` in
    `game/campaign.py`, which is fine on the machine holding the checkout and wrong
    everywhere else. A hosted service (P6.7) keeps its data in a volume that survives
    the container being rebuilt, which is exactly the thing an image path cannot do.
    """

    dir: str = DEFAULT_CAMPAIGNS_DIR

    @field_validator("dir")
    @classmethod
    def _a_directory_that_was_actually_named(cls, value: str) -> str:
        """An empty string is the dangerous typo here, not a malformed one.

        `dir: ""` resolves to the repo root itself, which would scatter campaign
        directories through the checkout rather than failing.
        """
        directory = value.strip()
        if not directory:
            raise ValueError(
                f"campaigns.dir is empty — use a path, e.g. {DEFAULT_CAMPAIGNS_DIR!r}"
            )
        return directory


class LoggingConfig(_Strict):
    dir: str
    stamp_commit_sha: bool


class PriceEntry(_Strict):
    """USD per million tokens. Cache rates derive from `input` when omitted."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_write: float | None = Field(default=None, ge=0)
    cache_read: float | None = Field(default=None, ge=0)


class Config(_Strict):
    billing: BillingConfig
    seats: Seats
    ollama_endpoints: dict[str, str] = Field(default_factory=dict)
    pricing: dict[str, PriceEntry] = Field(default_factory=dict)
    gameplay: GameplayConfig
    campaigns: CampaignsConfig = Field(default_factory=CampaignsConfig)
    logging: LoggingConfig
    web: WebConfig = Field(default_factory=WebConfig)


def load_config(path: Path | str | None = None) -> Config:
    """Read and validate config.yaml. Raises on unknown or missing keys."""
    resolved = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with resolved.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config.model_validate(raw)


#: Matches the `default:` line inside the `billing:` block.
_BILLING_DEFAULT_RE = re.compile(r"^(?P<indent>\s+)default:\s*(?P<value>\S+)", re.MULTILINE)


def save_billing_default(billing: Billing, path: Path | str | None = None) -> bool:
    """Make this session's billing choice the sticky default (D-004).

    Rewrites the single `default:` line rather than re-serialising the file — a
    round-trip through pyyaml would strip every comment, and the comments in config.yaml
    are the only place several decisions are explained.
    """
    resolved = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    text = resolved.read_text(encoding="utf-8")

    match = _BILLING_DEFAULT_RE.search(text)
    if match is None or match.group("value") == billing.value:
        return False

    start, end = match.span()
    line = text[start:end].replace(match.group("value"), billing.value, 1)
    resolved.write_text(text[:start] + line + text[end:], encoding="utf-8")
    return True
