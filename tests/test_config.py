"""P0.1 smoke tests: the package imports and the real config.yaml validates."""

from __future__ import annotations

import os
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
    assert cfg.seats.utility_interactive.endpoint.startswith("http")
    assert cfg.seats.utility_batch.endpoint.startswith("http")


def test_ollama_endpoints_registry_covers_seat_endpoints():
    """OD-5: toto-llm and sam-pc are both registered from day one."""
    cfg = load_config()
    registered = set(cfg.ollama_endpoints.values())
    assert {"toto-llm", "sam-pc"} <= set(cfg.ollama_endpoints)
    assert cfg.seats.npc.endpoint in registered
    assert cfg.seats.utility_interactive.endpoint in registered
    assert cfg.seats.utility_batch.endpoint in registered


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


# --- .env loading ----------------------------------------------------------


def test_env_file_populates_the_environment(tmp_path, monkeypatch):
    """`.env.example` and the api adapter's error both promise this works."""
    from dndc.config import load_env_file

    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-ant-fake\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert load_env_file(env) == ["ANTHROPIC_API_KEY"]
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fake"


def test_a_real_environment_variable_wins(tmp_path, monkeypatch):
    """An explicitly exported key must not be replaced by a stale file."""
    from dndc.config import load_env_file

    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")

    assert load_env_file(env) == []
    assert os.environ["ANTHROPIC_API_KEY"] == "from-shell"


def test_comments_blanks_quotes_and_export_prefixes(tmp_path, monkeypatch):
    from dndc.config import load_env_file

    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        'QUOTED="quoted value"\n'
        "export EXPORTED=exported\n"
        "SPACED = spaced\n"
        "novalue\n",
        encoding="utf-8",
    )
    for name in ("QUOTED", "EXPORTED", "SPACED"):
        monkeypatch.delenv(name, raising=False)

    loaded = load_env_file(env)
    assert loaded == ["QUOTED", "EXPORTED", "SPACED"]
    assert os.environ["QUOTED"] == "quoted value"
    assert os.environ["EXPORTED"] == "exported"
    assert os.environ["SPACED"] == "spaced"


def test_a_missing_env_file_is_fine(tmp_path):
    from dndc.config import load_env_file

    assert load_env_file(tmp_path / "nope") == []


def test_the_env_path_resolves_against_the_repo_not_the_cwd():
    """`dndc` must work from any directory — that is the whole point of the fix."""
    from dndc.config import DEFAULT_CONFIG_PATH, DEFAULT_ENV_PATH

    assert DEFAULT_ENV_PATH.is_absolute()
    assert DEFAULT_ENV_PATH.parent == DEFAULT_CONFIG_PATH.parent


# --- the utility seat split (Fable, 2026-08-14) ----------------------------


def test_the_two_utility_seats_are_distinct_models():
    """The whole ruling: the sweep is gated and the table waits on it, the chronicle is
    ungated and comprehension-critical. One model cannot be right for both."""
    cfg = load_config()
    assert cfg.seats.utility_interactive.model != cfg.seats.utility_batch.model


def test_a_pre_split_config_fails_with_instructions(tmp_path):
    """Never migrated by mapping `utility` onto both seats — that would put the small
    model in the batch seat and silently undo the ruling, with the config looking
    upgraded."""
    bad = tmp_path / "config.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            billing: {default: api}
            seats:
              gm: {backend: gmbackend, model_default: m, model_threshold: m}
              npc: {backend: ollama, endpoint: "http://x", model: m}
              utility: {backend: ollama, endpoint: "http://x", model: m}
            gameplay: {scaffolding: high, play_mode: hotseat}
            logging: {dir: logs/, stamp_commit_sha: true}
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as caught:
        load_config(bad)
    assert "utility_interactive" in str(caught.value)
    assert "utility_batch" in str(caught.value)
