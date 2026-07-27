"""Typed loader for config.yaml.

Everything that names a model or an endpoint routes through here. Code must never
hardcode a model name or URL (CLAUDE.md, Model seats).
"""

from __future__ import annotations

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


class Config(_Strict):
    billing: BillingConfig
    seats: Seats
    ollama_endpoints: dict[str, str] = Field(default_factory=dict)
    gameplay: GameplayConfig
    logging: LoggingConfig


def load_config(path: Path | str | None = None) -> Config:
    """Read and validate config.yaml. Raises on unknown or missing keys."""
    resolved = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with resolved.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config.model_validate(raw)
