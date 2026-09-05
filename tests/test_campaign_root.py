"""P6.7a: campaign state stops being a path baked into the code.

`default_campaigns_root()` was `parents[3] / "campaigns"` — correct on the machine
holding the checkout and wrong everywhere else, which is a problem the moment a container
mounts a volume. It now resolves through config, and the tests that matter are the ones
that fail if that resolution stops being reachable from every call site:
`test_the_shipped_config_still_points_beside_the_code` pins today's behaviour, and the
`test_*_follows_the_configured_root_without_being_told` group is the claim that no caller
has to remember to thread a root.

The other half is precedence. The environment beats config.yaml deliberately — the volume
a container mounts is not something an image can know — and the tests say so out loud,
because getting that backwards would mean a deployed session writing into the image and
losing the evening on the next `docker compose up`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dndc.config import (
    CAMPAIGNS_DIR_ENV,
    DEFAULT_CAMPAIGNS_DIR,
    CampaignsConfig,
    Config,
    load_config,
)
from dndc.game import campaign as campaign_module
from dndc.game.campaign import (
    CAMPAIGNS_DIRNAME,
    campaign_dir,
    configured_campaigns_dir,
    create_campaign,
    default_campaigns_root,
    list_campaigns,
    load_campaign,
    resolve_campaigns_root,
)
from dndc.game.creation import load_campaign_canon
from dndc.game.saves import SaveStore

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_inherited_override(monkeypatch):
    """The env var is process-wide; a test that sets it must not leak into the next."""
    monkeypatch.delenv(CAMPAIGNS_DIR_ENV, raising=False)


# --- the shipped default -----------------------------------------------------------


def test_the_shipped_config_still_points_beside_the_code():
    """Nothing has moved yet. The eviction is P6.7c's, once a volume exists to move to."""
    assert load_config().campaigns.dir == DEFAULT_CAMPAIGNS_DIR
    assert default_campaigns_root() == REPO / CAMPAIGNS_DIRNAME


def test_a_config_written_before_this_key_existed_still_loads():
    raw = load_config().model_dump()
    del raw["campaigns"]
    assert Config.model_validate(raw).campaigns.dir == DEFAULT_CAMPAIGNS_DIR


def test_an_empty_directory_is_refused_rather_than_meaning_the_repo_root():
    with pytest.raises(ValidationError, match="campaigns.dir is empty"):
        CampaignsConfig(dir="   ")


# --- resolution --------------------------------------------------------------------


def test_a_relative_directory_resolves_against_the_repo_not_the_working_directory(tmp_path):
    assert resolve_campaigns_root("campaigns/") == REPO / "campaigns"
    assert resolve_campaigns_root("saves/here", root=tmp_path) == tmp_path / "saves" / "here"


def test_an_absolute_directory_is_taken_as_given(tmp_path):
    assert resolve_campaigns_root(str(tmp_path)) == tmp_path
    assert resolve_campaigns_root(str(tmp_path), root=Path("/ignored")) == tmp_path


def test_a_tilde_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert resolve_campaigns_root("~/dnd") == tmp_path / "dnd"


# --- precedence --------------------------------------------------------------------


def test_the_environment_beats_config_because_it_is_what_a_container_has(monkeypatch, tmp_path):
    monkeypatch.setenv(CAMPAIGNS_DIR_ENV, str(tmp_path))
    assert configured_campaigns_dir() == str(tmp_path)
    assert default_campaigns_root() == tmp_path


def test_a_blank_environment_variable_is_not_an_override(monkeypatch):
    monkeypatch.setenv(CAMPAIGNS_DIR_ENV, "   ")
    assert configured_campaigns_dir() == DEFAULT_CAMPAIGNS_DIR


def test_an_explicit_root_argument_still_wins_over_both(monkeypatch, tmp_path):
    """The library seam predates the config key and keeps working; tests rely on it."""
    monkeypatch.setenv(CAMPAIGNS_DIR_ENV, str(tmp_path / "env"))
    assert campaign_dir("the-salt-road", tmp_path / "explicit") == tmp_path / "explicit" / "the-salt-road"


def test_a_missing_config_falls_back_rather_than_crashing(monkeypatch, tmp_path):
    """A checkout without config.yaml is still a usable library."""
    monkeypatch.setattr(campaign_module, "DEFAULT_CONFIG_PATH", tmp_path / "absent.yaml")
    assert configured_campaigns_dir() == DEFAULT_CAMPAIGNS_DIR


def test_an_invalid_config_raises_instead_of_silently_choosing_a_directory(monkeypatch, tmp_path):
    """The opposite of the P6.6 bind: a wrong answer that reports success is the bug."""
    broken = tmp_path / "config.yaml"
    broken.write_text("billing: {}\n", encoding="utf-8")
    monkeypatch.setattr(campaign_module, "DEFAULT_CONFIG_PATH", broken)
    with pytest.raises(ValidationError):
        configured_campaigns_dir()


# --- the claim that no call site has to remember ------------------------------------


@pytest.fixture()
def elsewhere(monkeypatch, tmp_path):
    """A campaigns root that is nowhere near the checkout, set the way a container sets it."""
    root = tmp_path / "data" / "campaigns"
    monkeypatch.setenv(CAMPAIGNS_DIR_ENV, str(root))
    return root


def test_creating_and_reading_a_campaign_follows_the_configured_root_without_being_told(elsewhere):
    created = create_campaign("The Salt Road", players=["Kelly"])
    assert (elsewhere / "the-salt-road" / "campaign.yaml").exists()
    assert load_campaign("the-salt-road").name == created.name
    assert [c.slug for c in list_campaigns()] == ["the-salt-road"]


def test_saves_follow_the_configured_root_without_being_told(elsewhere):
    create_campaign("The Salt Road")
    store = SaveStore.for_campaign("the-salt-road")
    assert elsewhere in store.path.parents


def test_the_canon_ledger_follows_the_configured_root_without_being_told(elsewhere):
    create_campaign("The Salt Road")
    (elsewhere / "the-salt-road" / "canon.yaml").write_text("entries: []\n", encoding="utf-8")
    assert load_campaign_canon("the-salt-road").entries == []


def test_the_repo_is_untouched_while_the_override_is_in_force(elsewhere):
    """The whole point: an evening on the VM must not write into the checkout."""
    before = sorted(p.name for p in (REPO / CAMPAIGNS_DIRNAME).iterdir())
    create_campaign("A Campaign That Must Not Land Here")
    after = sorted(p.name for p in (REPO / CAMPAIGNS_DIRNAME).iterdir())
    assert before == after
