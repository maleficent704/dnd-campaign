"""Typed loader for config.yaml.

Everything that names a model or an endpoint routes through here. Code must never
hardcode a model name or URL (CLAUDE.md, Model seats).
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


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
    utility: OllamaSeat


class GameplayConfig(_Strict):
    scaffolding: Literal["high", "low", "off"]
    play_mode: Literal["hotseat", "web"]


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
    logging: LoggingConfig


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
