"""P0.5: campaign scaffolding and the CLI command surface."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from dndc.game import campaign as campaign_module
from dndc.game.campaign import (
    CampaignError,
    create_campaign,
    list_campaigns,
    load_campaign,
)
from dndc.game.cli import main
from dndc.logging import read_log
from dndc.schema.campaign import Campaign, slugify

SHEET = """
name: Bramble Tealeaf
player: Sam
species: Halfling
character_class: Rogue
level: 3
background: Urchin
abilities: {str: 8, dex: 17, con: 14, int: 12, wis: 13, cha: 10}
proficiencies:
  saving_throws: [dex, int]
  skills: {stealth: expertise, perception: proficient}
  languages: [Common, Halfling]
hit_points: {maximum: 21, current: 18}
armor_class: 14
speed: 25
hit_dice: 3d8
inventory:
  - {name: Shortsword, weight: 2.0, equipped: true}
"""


@pytest.fixture
def sheet_path(tmp_path) -> Path:
    path = tmp_path / "bramble.yaml"
    path.write_text(SHEET, encoding="utf-8")
    return path


@pytest.fixture
def campaigns_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "campaigns"
    monkeypatch.setattr(campaign_module, "default_campaigns_root", lambda: root)
    return root


# --- slugs -----------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("The Hollow Road", "the-hollow-road"),
        ("  Spaced   Out  ", "spaced-out"),
        ("Ash & Ember!", "ash-ember"),
        ("Curse of the Elk-Lord", "curse-of-the-elk-lord"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


@pytest.mark.parametrize("reserved", ["nul", "CON", "aux", "com1", "LPT9", "prn"])
def test_windows_reserved_device_names_are_escaped(reserved):
    """A directory literally called `nul` is not creatable on this household's box."""
    slug = slugify(reserved)
    assert slug == f"{reserved.casefold()}-campaign"


def test_a_name_with_no_usable_characters_is_rejected():
    with pytest.raises(ValueError, match="no usable characters"):
        slugify("!!!")


# --- campaign creation -----------------------------------------------------


def test_create_campaign_lays_out_the_directory(campaigns_root):
    campaign = create_campaign("The Hollow Road", players=["Kelly", "Sam"])
    target = campaigns_root / "the-hollow-road"
    assert (target / "campaign.yaml").exists()
    assert (target / "characters").is_dir()
    assert (target / "saves").is_dir()
    assert campaign.players == ["Kelly", "Sam"]


def test_saves_dir_keeps_a_gitkeep_because_it_is_gitignored(campaigns_root):
    create_campaign("Keepsake")
    assert (campaigns_root / "keepsake" / "saves" / ".gitkeep").exists()


def test_create_campaign_refuses_to_overwrite(campaigns_root):
    """Overwriting would destroy sheets and, from Phase 2, the canon ledger."""
    create_campaign("The Hollow Road")
    with pytest.raises(CampaignError, match="refusing to overwrite"):
        create_campaign("The Hollow Road")


def test_differently_written_names_collide_on_slug(campaigns_root):
    create_campaign("The Hollow Road")
    with pytest.raises(CampaignError):
        create_campaign("the   hollow road")


def test_campaign_round_trips_through_yaml(campaigns_root):
    create_campaign("The Hollow Road", players=["Kelly"], scaffolding="low")
    loaded = load_campaign("the-hollow-road")
    assert loaded.name == "The Hollow Road"
    assert loaded.scaffolding == "low"
    assert loaded.players == ["Kelly"]


def test_campaign_yaml_is_hand_editable(campaigns_root):
    create_campaign("The Hollow Road")
    text = (campaigns_root / "the-hollow-road" / "campaign.yaml").read_text(encoding="utf-8")
    assert "!!python" not in text
    assert "name: The Hollow Road" in text


def test_listing_campaigns(campaigns_root):
    create_campaign("Alpha")
    create_campaign("Beta")
    assert [c.slug for c in list_campaigns()] == ["alpha", "beta"]


def test_listing_is_empty_before_any_exist(campaigns_root):
    assert list_campaigns() == []


def test_campaign_model_round_trip():
    campaign = Campaign(name="X", slug="x", created=date(2026, 7, 27))
    assert Campaign.from_yaml(campaign.to_yaml()) == campaign


# --- cli: roll -------------------------------------------------------------


def test_roll_is_reproducible_from_a_seed(capsys):
    assert main(["roll", "2d6+3", "--seed", "42"]) == 0
    first = capsys.readouterr().out
    assert main(["roll", "2d6+3", "--seed", "42"]) == 0
    assert capsys.readouterr().out == first


def test_roll_reports_the_seed_even_when_not_given(capsys):
    """An unrecorded roll is not reproducible, which defeats the point."""
    assert main(["roll", "1d4"]) == 0
    assert "seed" in capsys.readouterr().out


def test_roll_rejects_a_malformed_expression(capsys):
    assert main(["roll", "2d6 3"]) == 1
    assert "error" in capsys.readouterr().out


def test_roll_with_advantage_shows_both_faces(capsys):
    assert main(["roll", "d20", "--advantage", "--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert "advantage" in out and "->" in out


def test_roll_can_write_a_session_log(tmp_path, monkeypatch, capsys):
    import dndc.game.cli as cli

    monkeypatch.setattr(cli, "resolve_log_dir", lambda *a, **k: tmp_path)
    assert main(["roll", "2d6+3", "--seed", "42", "--log"]) == 0

    (log_file,) = list(tmp_path.glob("*.jsonl"))
    events = read_log(log_file)
    assert [e.type.value for e in events] == ["session_meta", "rules_resolution"]

    meta, resolution = events
    assert meta.seed == 42
    assert meta.seats["gm"].model  # resolved from config.yaml, never hardcoded
    assert resolution.roll.expression == "2d6+3"
    assert resolution.seed == 42


# --- cli: sheet ------------------------------------------------------------


def test_sheet_show(sheet_path, capsys):
    assert main(["sheet", "show", str(sheet_path)]) == 0
    out = capsys.readouterr().out
    assert "Bramble Tealeaf" in out
    assert "+7" in out  # Stealth: Dex +3 with expertise at PB 2


def test_sheet_validate_accepts_a_good_sheet(sheet_path, capsys):
    assert main(["sheet", "validate", str(sheet_path)]) == 0
    assert "valid" in capsys.readouterr().out


def test_sheet_validate_reports_the_offending_field(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(SHEET.replace("current: 18", "current: 99"), encoding="utf-8")
    assert main(["sheet", "validate", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "hit_points" in out and "exceeds maximum" in out


def test_sheet_missing_file(tmp_path, capsys):
    assert main(["sheet", "show", str(tmp_path / "nope.yaml")]) == 1
    assert "no sheet at" in capsys.readouterr().out


def test_sheet_malformed_yaml(tmp_path, capsys):
    broken = tmp_path / "broken.yaml"
    broken.write_text("name: [unclosed\n", encoding="utf-8")
    assert main(["sheet", "show", str(broken)]) == 1
    assert "could not read" in capsys.readouterr().out


# --- cli: campaigns --------------------------------------------------------


def test_new_campaign_command(campaigns_root, capsys):
    assert main(["new-campaign", "The Hollow Road", "--player", "Kelly"]) == 0
    out = capsys.readouterr().out
    assert "created" in out
    assert (campaigns_root / "the-hollow-road" / "campaign.yaml").exists()


def test_new_campaign_command_refuses_a_duplicate(campaigns_root, capsys):
    main(["new-campaign", "The Hollow Road"])
    capsys.readouterr()
    assert main(["new-campaign", "The Hollow Road"]) == 1
    assert "already exists" in capsys.readouterr().out


def test_new_campaign_rejects_an_unusable_name(campaigns_root, capsys):
    assert main(["new-campaign", "!!!"]) == 1
    assert "no usable characters" in capsys.readouterr().out


def test_campaigns_command_lists_them(campaigns_root, capsys):
    main(["new-campaign", "Alpha"])
    capsys.readouterr()
    assert main(["campaigns"]) == 0
    assert "alpha" in capsys.readouterr().out


def test_campaigns_command_when_none_exist(campaigns_root, capsys):
    assert main(["campaigns"]) == 0
    assert "no campaigns yet" in capsys.readouterr().out


# --- cli: general ----------------------------------------------------------


def test_bare_invocation_prints_help(capsys):
    assert main([]) == 0
    assert "usage: dndc" in capsys.readouterr().out


def test_check_config_still_works(capsys):
    assert main(["--check-config"]) == 0
    assert "billing default" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert "dndc" in capsys.readouterr().out
