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


def test_gm_show_prompt_needs_no_backend(capsys, tmp_path):
    """P1.2: inspecting the assembled prompt must not need a key, a login, or a
    billing decision — it is the offline debugging tool for the prompt builder."""
    canon = tmp_path / "canon.yaml"
    canon.write_text(
        "entries:\n"
        "  - id: c1\n"
        "    text: The gorge bridge is rotting.\n",
        encoding="utf-8",
    )

    code = main([
        "gm", "I test the first plank.",
        "--show-prompt",
        "--campaign-name", "The Salt Road",
        "--scene", "A rope bridge at dusk.",
        "--canon", str(canon),
        "--resolution", "Perception check: 9 vs DC 12 - failure",
        "--scaffolding", "high",
    ])
    out = capsys.readouterr().out

    assert code == 0
    assert "[[CHECK:" in out                      # the system template
    assert "The Salt Road" in out                 # volatile campaign state
    assert "The gorge bridge is rotting." in out  # the ledger was loaded
    assert "A rope bridge at dusk." in out
    assert "Perception check: 9 vs DC 12 - failure" in out
    assert "I test the first plank." in out


def test_gm_rejects_an_unknown_scaffolding_level(capsys):
    with pytest.raises(SystemExit):
        main(["gm", "hello", "--show-prompt", "--scaffolding", "medium"])


# --- /switch name matching (P1.5 live bug) ---------------------------------


@pytest.fixture
def party():
    from dndc.gm import PartyMember

    return [
        PartyMember(name="Corin Vale", player="Kelly"),
        PartyMember(name="Brother Hammond", player="Sam"),
    ]


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Corin Vale", "Corin Vale"),          # the only form that used to work
        ("corin", "Corin Vale"),               # what Kelly actually typed
        ("CORIN", "Corin Vale"),
        ("  hammond  ", "Brother Hammond"),    # a surname, not the first word
        ("cor", "Corin Vale"),                 # prefix
        ("brother ham", "Brother Hammond"),    # prefix of the whole name
        ("Kelly", "Corin Vale"),               # the player, not the character
        ("sam", "Brother Hammond"),
    ],
)
def test_switch_matches_the_way_a_person_says_a_name(party, query, expected):
    from dndc.game.cli import resolve_member

    assert [member.name for member in resolve_member(query, party)] == [expected]


def test_switch_reports_ambiguity_instead_of_guessing(party):
    from dndc.game.cli import resolve_member
    from dndc.gm import PartyMember

    crowded = [*party, PartyMember(name="Brother Aldric", player="Nat")]
    matches = resolve_member("brother", crowded)
    assert {member.name for member in matches} == {"Brother Hammond", "Brother Aldric"}


def test_switch_prefers_the_exact_name_over_a_longer_one_it_prefixes(party):
    """A unique first name must not be made ambiguous by a name it happens to prefix."""
    from dndc.game.cli import resolve_member
    from dndc.gm import PartyMember

    crowded = [*party, PartyMember(name="Corinth Bell", player="Nat")]
    assert [m.name for m in resolve_member("corin", crowded)] == ["Corin Vale"]


def test_switch_prefers_a_character_over_a_player_of_the_same_name():
    from dndc.game.cli import resolve_member
    from dndc.gm import PartyMember

    party = [
        PartyMember(name="Sam", player="Kelly"),
        PartyMember(name="Brother Hammond", player="Sam"),
    ]
    assert [m.name for m in resolve_member("sam", party)] == ["Sam"]


@pytest.mark.parametrize("query", ["", "   ", "nobody", "zzz"])
def test_switch_matches_nothing_it_should_not(party, query):
    from dndc.game.cli import resolve_member

    assert resolve_member(query, party) == []


# --- /scaffolding (OD-15) --------------------------------------------------


def _command(text: str, campaign, builder):
    from rich.console import Console

    from dndc.game.cli import _play_command

    console = Console(force_terminal=False, no_color=True, width=200)
    with console.capture() as captured:
        outcome = _play_command(console, text, campaign, builder)
    return outcome, captured.get()


@pytest.fixture
def play_context(party):
    from dndc.gm import CampaignContext, GMPromptBuilder

    return CampaignContext(name="The Salt Road", party=list(party)), GMPromptBuilder(
        scaffolding="high"
    )


def test_scaffolding_command_changes_the_level_mid_session(play_context):
    campaign, builder = play_context
    outcome, out = _command("/scaffolding low", campaign, builder)

    assert builder.scaffolding == "low"
    assert "low" in out
    assert not outcome.quit and outcome.active is None
    # The directive the GM actually receives has to have changed with it.
    assert "no longer need a menu" in builder.system()


def test_scaffolding_command_reports_the_level_when_asked_bare(play_context):
    campaign, builder = play_context
    _, out = _command("/scaffolding", campaign, builder)

    assert "high" in out
    assert builder.scaffolding == "high"


def test_scaffolding_command_rejects_a_level_that_does_not_exist(play_context):
    campaign, builder = play_context
    _, out = _command("/scaffolding medium", campaign, builder)

    assert builder.scaffolding == "high"
    assert "medium" in out


def test_switch_command_hands_over_on_a_first_name(play_context):
    campaign, builder = play_context
    outcome, out = _command("/switch hammond", campaign, builder)

    assert outcome.active == "Brother Hammond"
    assert "Sam" in out


def test_switch_command_names_the_party_when_it_cannot_match(play_context):
    campaign, builder = play_context
    outcome, out = _command("/switch Gorbo", campaign, builder)

    assert outcome.active is None
    assert "Corin Vale" in out and "Brother Hammond" in out


def test_quit_still_ends_the_loop(play_context):
    campaign, builder = play_context
    assert _command("/quit", campaign, builder)[0].quit


@pytest.mark.parametrize(
    "turns,level,expected",
    [
        (0, "high", False),
        (1, "high", False),
        (12, "high", True),
        (24, "low", True),
        (12, "off", False),   # nothing left to turn down
    ],
)
def test_the_chrome_hints_periodically_never_the_gm(turns, level, expected):
    """OD-11's split: the GM may not mention the interface, so the CLI must."""
    from dndc.game.cli import should_hint_scaffolding

    assert should_hint_scaffolding(turns, level) is expected


def test_no_prompt_template_mentions_the_scaffolding_command():
    """If the GM knew the command existed it would eventually offer it in prose."""
    from dndc.gm.context import SCAFFOLDING_TEMPLATES
    from dndc.gm.templates import render_template

    for name in SCAFFOLDING_TEMPLATES.values():
        assert "/scaffolding" not in render_template(name)


def _streamed(chunks) -> str:
    from rich.console import Console

    from dndc.game.cli import _NarrationStream

    console = Console(force_terminal=False, no_color=True, width=200)
    stream = _NarrationStream(console)
    with console.capture() as captured:
        for chunk in chunks:
            stream.feed(chunk)
        stream.finish()
    return captured.get()


def test_stream_suppresses_the_check_tag():
    """Players must never see the machine instruction mid-sentence."""
    out = _streamed(["You creep forward.\n\n", "[[CHECK: Stealth DC 14 — seen]]"])
    assert "You creep forward." in out
    assert "CHECK" not in out


def test_stream_suppresses_a_tag_split_across_chunks():
    """Real streaming splits wherever it likes, including mid-tag."""
    out = _streamed(["You creep.", " [[CH", "ECK: Stea", "lth DC 14]]", " "])
    assert "You creep." in out
    assert "CHECK" not in out and "Stealth" not in out


def test_stream_still_passes_ordinary_brackets_through():
    out = _streamed(["The sign reads [CLOSED] in faded paint."])
    assert "[CLOSED]" in out


def test_stream_flushes_a_trailing_bracket():
    out = _streamed(["A lone bracket ["])
    assert out.endswith("[")


def test_stream_suppresses_the_creation_tags_too():
    """P1.4 added `[[PROPOSE:` and `[[FACT:`; the filter is on `[[`, not on tag names."""
    out = _streamed(["Here you go. ", "[[PROPOSE:\nname: X\n]]", " Sound right?"])
    assert "Here you go." in out and "Sound right?" in out
    assert "PROPOSE" not in out and "name: X" not in out


def test_stream_closes_the_gap_a_suppressed_tag_leaves():
    """The whitespace around a tag was spacing out the tag, not the prose."""
    out = _streamed(["It is done.\n\n", "[[FACT: He hates boats.]]", "\n\nWhat next?"])
    assert out == "It is done.\n\nWhat next?"


def test_stream_keeps_a_single_space_when_a_tag_was_mid_line():
    out = _streamed(["Noted. ", "[[FACT: X.]]", " Now, the road."])
    assert out == "Noted. Now, the road."


def test_play_needs_a_party_from_somewhere(campaigns_root, capsys):
    """`--character` stopped being required in P1.4; the party still has to exist."""
    assert main(["play", "--no-prompt"]) == 1
    assert "no characters loaded" in capsys.readouterr().out


def test_play_and_gm_load_a_campaign_directory(campaigns_root, sheet_path, capsys, tmp_path):
    """P1.4 wiring: --campaign reads the party and canon co-creation wrote."""
    from dndc.game.campaign import campaign_dir
    from dndc.game.creation import CANON_FILENAME
    from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
    from dndc.schema.sheet import CharacterSheet

    main(["new-campaign", "The Hollow Road", "--player", "Sam"])
    target = campaign_dir("the-hollow-road")
    CharacterSheet.load(sheet_path).save(target / "characters" / "bramble.yaml")
    ledger = CanonLedger()
    ledger.add(
        CanonEntry(id="pc-bramble-1", text="Bramble grew up on the docks.",
                   scope=CanonScope.CHARACTER, subject="Bramble Tealeaf")
    )
    ledger.save(target / CANON_FILENAME)
    capsys.readouterr()

    assert main([
        "gm", "I look around.", "--show-prompt", "--campaign", "the-hollow-road",
    ]) == 0
    out = capsys.readouterr().out
    assert "The Hollow Road" in out
    assert "Bramble Tealeaf" in out                    # party, from the sheet on disk
    assert "Bramble grew up on the docks." in out      # canon, from the ledger on disk


def test_a_missing_campaign_is_reported(campaigns_root, capsys):
    assert main(["gm", "hi", "--show-prompt", "--campaign", "nope"]) == 1
    assert "error" in capsys.readouterr().out


def test_create_character_requires_a_campaign_and_a_player(capsys):
    assert main(["create-character", "--player", "Kelly"]) == 1
    assert "--campaign" in capsys.readouterr().out


def test_create_character_show_prompt_needs_no_backend_or_campaign(capsys):
    """The offline inspector, same as `gm --show-prompt` (P1.2)."""
    assert main(["create-character", "--show-prompt"]) == 0
    out = capsys.readouterr().out
    assert "[[PROPOSE:" in out and "[[FACT:" in out
    assert "Fighter" in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert "dndc" in capsys.readouterr().out


# --- canon display (P2.2) --------------------------------------------------


def _canon_output(entries) -> str:
    from rich.console import Console

    from dndc.game.cli import _render_canon

    console = Console(force_terminal=False, no_color=True, width=200)
    with console.capture() as captured:
        _render_canon(console, entries)
    return captured.get()


def test_established_canon_is_shown_to_the_table():
    from dndc.gm.canon import CanonEntry

    output = _canon_output([CanonEntry(id="world-1", text="The gate is barred at dusk.")])
    assert "The gate is barred at dusk." in output


def test_a_gm_only_fact_is_never_displayed():
    """The chrome may not leak what the prompt withholds — OD-11's split cuts both ways."""
    from dndc.gm.canon import CanonEntry, CanonScope

    secret = CanonEntry(
        id="gm-1", text="The reeve took the bribe.", scope=CanonScope.GM_ONLY
    )
    assert _canon_output([secret]) == ""


def test_a_hidden_fact_is_not_even_counted():
    """"1 fact recorded (hidden)" still tells the players a secret was just written."""
    from dndc.gm.canon import CanonEntry, CanonScope

    entries = [
        CanonEntry(id="w-1", text="The gate is barred."),
        CanonEntry(id="gm-1", text="The reeve took the bribe.", scope=CanonScope.GM_ONLY),
    ]
    output = _canon_output(entries)
    assert "The gate is barred." in output
    assert "bribe" not in output
    assert "1" not in output and "hidden" not in output.lower()
