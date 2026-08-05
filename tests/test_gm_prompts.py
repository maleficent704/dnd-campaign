"""P1.2 — GM prompt assembly.

The assertions that matter here are about *content reaching the prompt*, not about
prose. A prompt builder fails silently: a renamed placeholder or a dropped ledger keeps
producing a perfectly plausible prompt that is missing the campaign.
"""

from __future__ import annotations

import pytest

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope, render_entries
from dndc.gm.context import (
    DEFAULT_WINDOW,
    SCAFFOLDING_TEMPLATES,
    CampaignContext,
    GMPromptBuilder,
    PartyMember,
    Turn,
)
from dndc.gm.templates import PROMPTS_DIR, TemplateError, load_template, placeholders, render
from dndc.models.base import Role
from dndc.models.mock import MockBackend
from dndc.schema.sheet import AbilityScores, CharacterSheet, HitPoints


# --- the renderer ----------------------------------------------------------


def test_render_substitutes_placeholders():
    assert render("hello {{ name }}", name="world") == "hello world"


def test_render_tolerates_whitespace_in_the_placeholder():
    assert render("a {{name}} b {{  name  }}", name="x") == "a x b x"


def test_render_rejects_a_missing_value():
    with pytest.raises(TemplateError, match="needs values for: scene"):
        render("{{ scene }} and {{ canon }}", canon="x")


def test_render_rejects_an_unused_value():
    """The failure mode that matters: a rename silently drops content from the prompt."""
    with pytest.raises(TemplateError, match="no placeholder for: ledger"):
        render("{{ canon }}", canon="x", ledger="the whole campaign")


def test_render_leaves_literal_braces_alone():
    """Prompt prose contains dice notation and JSON; `str.format` would choke on it."""
    template = "roll {1d20+5} then {{ verb }}"
    assert render(template, verb="narrate") == "roll {1d20+5} then narrate"


def test_render_collapses_the_gap_left_by_an_empty_section():
    assert render("a\n\n{{ mid }}\n\nb", mid="") == "a\n\nb"


def test_unknown_template_lists_what_exists():
    with pytest.raises(TemplateError, match="system_core"):
        load_template("no_such_template")


def test_every_template_on_disk_is_loadable():
    names = sorted(path.stem for path in PROMPTS_DIR.glob("*.md"))
    assert names, "no prompt templates found"
    for name in names:
        assert load_template(name).strip()


# --- the canon ledger stub -------------------------------------------------


def test_entry_render_marks_gm_only_secrets():
    entry = CanonEntry(id="e1", text="The steward is the informant.", scope=CanonScope.GM_ONLY)
    assert entry.render() == "- [GM ONLY] The steward is the informant."


def test_entry_render_attributes_an_npc_belief():
    entry = CanonEntry(
        id="e2", text="the bridge is safe", scope=CanonScope.NPC_BELIEF, subject="Hilda"
    )
    assert entry.render() == "- [Hilda believes] the bridge is safe"


def test_ledger_rejects_a_duplicate_id():
    ledger = CanonLedger()
    ledger.add(CanonEntry(id="e1", text="a"))
    with pytest.raises(ValueError, match="already used"):
        ledger.add(CanonEntry(id="e1", text="b"))


def test_ledger_round_trips_through_yaml(tmp_path):
    ledger = CanonLedger()
    ledger.add(CanonEntry(id="e1", text="Thornwake sits in a caldera.", session="s1", turn=4))
    ledger.add(CanonEntry(id="e2", text="The steward lies.", scope=CanonScope.GM_ONLY))

    path = ledger.save(tmp_path / "canon.yaml")
    reloaded = CanonLedger.load(path)

    assert [e.id for e in reloaded] == ["e1", "e2"]
    assert reloaded.get("e1").turn == 4
    assert reloaded.get("e2").scope is CanonScope.GM_ONLY


def test_loading_a_missing_ledger_gives_an_empty_one(tmp_path):
    assert len(CanonLedger.load(tmp_path / "absent.yaml")) == 0


def test_scoped_filters_by_scope():
    ledger = CanonLedger()
    ledger.add(CanonEntry(id="w", text="a", scope=CanonScope.WORLD))
    ledger.add(CanonEntry(id="s", text="b", scope=CanonScope.GM_ONLY))
    assert [e.id for e in ledger.scoped([CanonScope.WORLD])] == ["w"]


def test_empty_ledger_renders_an_explicit_marker():
    """Better than an absent section: it tells the GM the campaign is genuinely new."""
    assert "nothing established yet" in render_entries([])


def test_render_entries_groups_by_scope():
    entries = [
        CanonEntry(id="a", text="secret", scope=CanonScope.GM_ONLY),
        CanonEntry(id="b", text="world fact", scope=CanonScope.WORLD),
        CanonEntry(id="c", text="another secret", scope=CanonScope.GM_ONLY),
    ]
    lines = render_entries(entries).splitlines()
    assert lines[0].endswith("world fact")
    assert all("[GM ONLY]" in line for line in lines[1:])


# --- the system prompt -----------------------------------------------------


@pytest.fixture
def builder():
    return GMPromptBuilder(scaffolding="high")


def test_system_prompt_carries_the_never_invent_mechanics_rule(builder):
    system = builder.system().lower()
    assert "never" in system
    assert "roll" in system
    assert "engine" in system


def test_system_prompt_specifies_the_check_request_form(builder):
    """P1.3 parses this; the GM has to be told the exact shape now (D-001 boundary)."""
    assert "[[CHECK:" in builder.system()


def test_system_prompt_separates_true_from_known(builder):
    """A live call handed the party a canon fact described as hidden, unprompted — the
    prompt said facts are true but never said they are not automatically known."""
    system = builder.system().lower()
    assert "not the same as being known" in system
    assert "concealed" in system


def test_system_prompt_forbids_published_modules(builder):
    """D-007 — original content only."""
    assert "module" in builder.system().lower()


@pytest.mark.parametrize("level", sorted(SCAFFOLDING_TEMPLATES))
def test_each_scaffolding_level_produces_a_distinct_system_prompt(level):
    prompts = {lvl: GMPromptBuilder(scaffolding=lvl).system() for lvl in SCAFFOLDING_TEMPLATES}
    others = [text for lvl, text in prompts.items() if lvl != level]
    assert all(prompts[level] != other for other in others)


def test_high_scaffolding_demands_the_menu_is_not_exhaustive():
    """D-006's load-bearing half: the options must never read as a fence."""
    system = GMPromptBuilder(scaffolding="high").system().lower()
    assert "not exhaustive" in system or "anything else" in system


def test_off_scaffolding_does_not_ask_for_options():
    system = GMPromptBuilder(scaffolding="off").system().lower()
    assert "do not surface options" in system


def test_unknown_scaffolding_level_is_rejected():
    with pytest.raises(ValueError, match="unknown scaffolding level"):
        GMPromptBuilder(scaffolding="medium")


def test_system_prompt_is_stable_across_turns(builder):
    """It is the cache prefix — if it varies per turn, caching silently never hits."""
    assert builder.system() == builder.system()


# --- campaign state --------------------------------------------------------


def _campaign() -> CampaignContext:
    campaign = CampaignContext(
        name="The Salt Road",
        premise="Caravan guards on a failing trade route.",
        scene="A rope bridge over the Cauldron gorge, at dusk.",
        party=[
            PartyMember(
                name="Brannoc", player="Kelly", descriptor="level 2 human fighter",
                hp_current=9, hp_max=14,
            ),
            PartyMember(name="Vess", player="Sam", descriptor="level 2 elf wizard"),
        ],
    )
    campaign.ledger.add(CanonEntry(id="c1", text="The gorge bridge is rotting."))
    campaign.ledger.add(
        CanonEntry(id="c2", text="The caravan master is a smuggler.", scope=CanonScope.GM_ONLY)
    )
    return campaign


def test_campaign_state_contains_every_moving_part(builder):
    state = builder.campaign_state(_campaign())
    assert "The Salt Road" in state
    assert "failing trade route" in state
    assert "Cauldron gorge" in state
    assert "Brannoc" in state
    assert "9/14 HP" in state
    assert "The gorge bridge is rotting." in state
    assert "[GM ONLY] The caravan master is a smuggler." in state


def test_party_member_renders_from_a_sheet():
    sheet = CharacterSheet(
        name="Brannoc",
        player="Kelly",
        species="Human",
        character_class="Fighter",
        level=2,
        abilities=AbilityScores(str=16, dex=12, con=14, int=10, wis=11, cha=8),
        hit_points=HitPoints(maximum=14, current=9),
        armor_class=16,
    )
    rendered = PartyMember.from_sheet(sheet).render()
    assert "Brannoc" in rendered
    assert "Kelly" in rendered
    assert "level 2 Human Fighter" in rendered
    assert "9/14 HP" in rendered


def test_a_downed_character_is_flagged():
    member = PartyMember(name="Vess", player="Sam", hp_current=0, hp_max=11)
    assert "unconscious" in member.render()


def test_empty_campaign_state_says_so_rather_than_going_blank(builder):
    state = builder.campaign_state(CampaignContext(name="Untitled"))
    assert "no characters created yet" in state
    assert "has not opened yet" in state
    assert "nothing established yet" in state


# --- turn assembly ---------------------------------------------------------


def test_turn_message_marks_resolutions_authoritative(builder):
    message = builder.turn_message(
        "I creep along the rail.",
        speaker="Kelly (Brannoc)",
        resolutions=("Stealth check: 17 vs DC 14 — success",),
    )
    assert message.role is Role.USER
    assert "Kelly (Brannoc)" in message.content
    assert "I creep along the rail." in message.content
    assert "Stealth check: 17 vs DC 14 — success" in message.content
    assert "authoritative" in message.content


def test_a_turn_with_no_resolutions_says_none(builder):
    message = builder.turn_message("I look around.")
    assert "none" in message.content.lower()


def test_build_splits_stable_from_volatile(builder):
    """The cache-prefix split: instructions in `system`, state in `system_volatile`."""
    request = builder.build(_campaign(), player_input="I cross the bridge.")

    assert "[[CHECK:" in request.system
    assert "The Salt Road" not in request.system

    assert "The Salt Road" in request.system_volatile
    assert "[[CHECK:" not in request.system_volatile


def test_build_puts_the_player_input_last(builder):
    request = builder.build(_campaign(), player_input="I cross the bridge.")
    assert request.messages[-1].role is Role.USER
    assert "I cross the bridge." in request.messages[-1].content


def test_full_system_joins_both_halves(builder):
    request = builder.build(_campaign(), player_input="hello")
    assert request.system in request.full_system
    assert request.system_volatile in request.full_system


# --- the recent window -----------------------------------------------------


def test_window_alternates_user_and_assistant():
    campaign = _campaign()
    campaign.record(Turn(player_input="I knock.", narration="The door opens."))
    campaign.record(Turn(player_input="I step in.", narration="Warm air, woodsmoke."))

    window = campaign.window()
    assert [m.role for m in window] == [Role.USER, Role.ASSISTANT, Role.USER, Role.ASSISTANT]
    assert "The door opens." in window[1].content


def test_window_is_bounded_not_a_growing_transcript():
    """D-002's prompt rule — this is the thing that bounds cost across a campaign."""
    campaign = _campaign()
    for index in range(50):
        campaign.record(Turn(player_input=f"turn {index}", narration=f"reply {index}"))

    builder = GMPromptBuilder(scaffolding="high", window=3)
    request = builder.build(campaign, player_input="now what?")

    # 3 past turns = 6 messages, plus this turn's input.
    assert len(request.messages) == 7
    assert "turn 46" not in request.messages[0].content
    assert "turn 47" in request.messages[0].content


def test_default_window_is_applied():
    campaign = _campaign()
    for index in range(DEFAULT_WINDOW + 5):
        campaign.record(Turn(player_input=f"t{index}", narration=f"n{index}"))
    assert len(campaign.window()) == DEFAULT_WINDOW * 2


def test_zero_window_sends_no_history():
    campaign = _campaign()
    campaign.record(Turn(player_input="a", narration="b"))
    assert campaign.window(0) == ()


# --- end to end through the mock seat --------------------------------------


def test_a_built_request_survives_the_round_trip_to_a_backend(builder):
    """Offline proof that assembly and the D-004 seam fit together."""
    backend = MockBackend(["The planks groan under your boot."])
    request = builder.build(
        _campaign(),
        player_input="I test the first plank.",
        resolutions=("Perception check: 9 vs DC 12 — failure",),
    )
    response = backend.generate(request)

    sent = backend.last_request
    assert "Perception check: 9 vs DC 12 — failure" in sent.messages[-1].content
    assert "The Salt Road" in sent.system_volatile
    assert response.text == "The planks groan under your boot."


def test_a_canon_write_does_not_disturb_the_cached_prefix(builder):
    """Why the split exists: new canon must not invalidate the instruction block."""
    campaign = _campaign()
    before = builder.build(campaign, player_input="x")

    campaign.ledger.add(CanonEntry(id="c3", text="The steward watched them leave."))
    after = builder.build(campaign, player_input="x")

    assert before.system == after.system
    assert before.system_volatile != after.system_volatile
