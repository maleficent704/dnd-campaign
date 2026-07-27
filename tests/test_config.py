"""P0.1 smoke tests: the package imports and the real config.yaml validates."""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

import dndc
from dndc.config import Billing, Config, load_config


def test_package_exposes_version():
    assert dndc.__version__


def test_repo_config_validates():
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.billing.default in Billing
    # Every seat names a model and, for local seats, an endpoint.
    assert cfg.seats.gm.model_default
    assert cfg.seats.gm.model_threshold
    assert cfg.seats.npc.endpoint.startswith("http")
    assert cfg.seats.utility.endpoint.startswith("http")


def test_ollama_endpoints_registry_covers_seat_endpoints():
    """OD-5: toto-llm and sam-pc are both registered from day one."""
    cfg = load_config()
    registered = set(cfg.ollama_endpoints.values())
    assert {"toto-llm", "sam-pc"} <= set(cfg.ollama_endpoints)
    assert cfg.seats.npc.endpoint in registered
    assert cfg.seats.utility.endpoint in registered


def test_unknown_key_is_rejected(tmp_path):
    """extra='forbid' — a typo in config.yaml must fail loudly, not silently default."""
    bad = tmp_path / "config.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            billing:
              default: api
            seats:
              gm: {backend: gmbackend, model_default: m, model_threshold: m}
              npc: {backend: ollama, endpoint: "http://x", model: m}
              utility: {backend: ollama, endpoint: "http://x", model: m}
            gameplay: {scaffolding: high, play_mode: hotseat}
            logging: {dir: "logs/", stamp_commit_sha: true, typo_here: 1}
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(bad)


def test_bad_scaffolding_value_is_rejected(tmp_path):
    """D-006: scaffolding is high | low | off."""
    bad = tmp_path / "config.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            billing:
              default: api
            seats:
              gm: {backend: gmbackend, model_default: m, model_threshold: m}
              npc: {backend: ollama, endpoint: "http://x", model: m}
              utility: {backend: ollama, endpoint: "http://x", model: m}
            gameplay: {scaffolding: medium, play_mode: hotseat}
            logging: {dir: "logs/", stamp_commit_sha: true}
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(bad)
