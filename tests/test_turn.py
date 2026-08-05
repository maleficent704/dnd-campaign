"""P1.3 — the turn loop, the check-request parser, and OD-11 severity.

The load-bearing assertions here are boundary assertions: that the GM never receives a
number, that the engine never takes a roll from the model, and that a model call always
leaves a terminal log row.
"""

from __future__ import annotations

import random

import pytest

from dndc.game.turn import MAX_GM_CALLS, TurnEngine
from dndc.gm.checkrequest import (
    CheckRequestError,
    find_check_request,
    find_check_requests,
    strip_check_requests,
)
from dndc.gm.context import CampaignContext, PartyMember
from dndc.logging import read_log
from dndc.models.base import GMBackendError, GMResponse, Role
from dndc.models.mock import MockBackend
from dndc.rules.checks import CheckResult, resolve_check
from dndc.rules.dice import Advantage, D20Result
from dndc.rules.severity import check_severity, damage_severity, describe_check
from dndc.schema.events import EventType
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    Proficiencies,
    Proficiency,
    Skill,
)


def sheet(name: str = "Brannoc", player: str = "Kelly", **overrides) -> CharacterSheet:
    data = dict(
        name=name,
        player=player,
        species="Human",
        character_class="Fighter",
        level=2,
        abilities=AbilityScores(str=16, dex=12, con=14, int=10, wis=11, cha=8),
        proficiencies=Proficiencies(
            saving_throws=["str", "con"],
            skills={Skill.ATHLETICS: Proficiency.PROFICIENT},
        ),
        hit_points=HitPoints(maximum=20, current=13),
        armor_class=16,
    )
    data.update(overrides)
    return CharacterSheet(**data)


def campaign_with(*members: PartyMember) -> CampaignContext:
    return CampaignContext(name="The Salt Road", scene="A flooded undercroft.", party=list(members))


def _engine(responses, log=None) -> TurnEngine:
    """A turn engine over a scripted GM, for the opening-scene tests."""
    return TurnEngine(
        backend=MockBackend(responses=responses),
        campaign=campaign_with(PartyMember(name="Brannoc", player="Kelly")),
        rng=random.Random(1),
        log=log,
    )


# --- parsing the check request ---------------------------------------------


def test_parses_ability_and_skill():
    request = find_check_request("[[CHECK: Dexterity (Stealth) DC 14 — the guard turns]]")
    assert request.ability.value == "dex"
    assert request.skill is Skill.STEALTH
    assert request.dc == 14
    assert request.stakes == "the guard turns"


def test_parses_a_bare_ability():
    request = find_check_request("[[CHECK: Strength DC 15 — the gate holds]]")
    assert request.ability.value == "str"
    assert request.skill is None


def test_parses_a_bare_skill_and_derives_its_ability():
    request = find_check_request("[[CHECK: Perception DC 12]]")
    assert request.skill is Skill.PERCEPTION
    assert request.ability.value == "wis"  # SKILL_ABILITY, not the model's opinion


def test_the_srd_mapping_wins_over_a_mismatched_ability():
    """If the GM pairs a skill with the wrong ability, the rules data is authoritative."""
    request = find_check_request("[[CHECK: Strength (Stealth) DC 12]]")
    assert request.skill is Skill.STEALTH
    assert request.ability.value == "dex"


@pytest.mark.parametrize(
    "text",
    [
        "[[CHECK: Dexterity (Stealth) DC 14 — stakes]]",
        "[[check: dexterity (stealth) dc 14 - stakes]]",
        "[[CHECK: Dexterity (Stealth) DC14 – stakes]]",
        "[[ CHECK : Dexterity (Stealth)  DC 14  — stakes ]]",
    ],
)
def test_surface_variation_is_tolerated(text):
    """The producer is a language model; rejecting a turn over an en dash is a bad trade."""
    request = find_check_request(text)
    assert request.skill is Skill.STEALTH
    assert request.dc == 14


def test_multi_word_skills_parse():
    request = find_check_request("[[CHECK: Sleight of Hand DC 13]]")
    assert request.skill is Skill.SLEIGHT_OF_HAND


def test_a_save_is_marked_as_one():
    request = find_check_request("[[CHECK: Constitution save DC 12 — you start coughing]]")
    assert request.is_save is True
    assert request.ability.value == "con"


def test_a_missing_dc_is_an_error_not_a_guess():
    """Inventing a DC would silently replace the judgment the GM was asked to make."""
    with pytest.raises(CheckRequestError, match="no DC"):
        find_check_request("[[CHECK: Stealth — the guard turns]]")


def test_an_unknown_ability_is_an_error():
    with pytest.raises(CheckRequestError, match="no ability or skill"):
        find_check_request("[[CHECK: Vibes DC 12]]")


def test_no_request_returns_none():
    assert find_check_request("The door swings open on a dark hall.") is None


def test_multiple_requests_are_all_found():
    text = "[[CHECK: Stealth DC 12]] and [[CHECK: Perception DC 10]]"
    assert len(find_check_requests(text)) == 2


def test_the_tag_is_stripped_from_narration():
    """It is machine instruction — leaving it in feeds it back as the GM's own voice."""
    text = "You creep forward.\n\n[[CHECK: Stealth DC 14 — the guard turns]]"
    assert strip_check_requests(text) == "You creep forward."


# --- severity (OD-11) ------------------------------------------------------


def _check_result(total: int, dc: int, success: bool) -> CheckResult:
    return CheckResult(
        roll=D20Result(
            rolls=(total,), natural=total, modifier=0, total=total,
            advantage=Advantage.NORMAL,
        ),
        dc=dc,
        success=success,
        kind="check",
        ability="str",
    )


@pytest.mark.parametrize(
    "total,dc,success,expected",
    [
        (25, 15, True, "succeeded decisively"),
        (17, 15, True, "succeeded, but only barely"),
        (21, 15, True, "succeeded"),
        (14, 15, False, "failed, but only just"),
        (5, 15, False, "failed badly"),
        (9, 15, False, "failed"),
    ],
)
def test_check_severity_bands(total, dc, success, expected):
    assert check_severity(_check_result(total, dc, success)) == expected


def test_damage_severity_is_relative_to_the_character():
    """6 damage is a scratch to one character and near-lethal to another."""
    assert damage_severity(6, current_hp=54, maximum_hp=60) == "barely scratched"
    assert damage_severity(6, current_hp=2, maximum_hp=8) == "gravely wounded and barely standing"


def test_being_dropped_is_called_out():
    assert "unconscious" in damage_severity(9, current_hp=0, maximum_hp=20)


def test_describe_check_carries_no_numbers():
    """The point of OD-11: the GM cannot restate a value it was never given."""
    result = _check_result(5, 15, False)
    described = describe_check(result, "Brannoc")
    assert "failed badly" in described
    assert "5" not in described
    assert "15" not in described


# --- the turn loop ---------------------------------------------------------


def test_a_turn_with_no_check_makes_one_call():
    backend = MockBackend(["The door opens on a dark hall."])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(1))

    result = engine.run("I open the door.", player="Kelly")

    assert len(backend.calls) == 1
    assert result.narration == "The door opens on a dark hall."
    assert result.mechanics == []


def test_a_check_request_triggers_a_second_call_with_the_outcome():
    backend = MockBackend([
        "You wedge your fingers under the gate.\n\n[[CHECK: Strength DC 15 — it holds]]",
        "The iron shifts an inch, then slams back down.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7))

    result = engine.run("I force the portcullis.", player="Kelly", sheet=sheet())

    assert len(backend.calls) == 2
    assert result.adjudication.dc == 15
    assert len(result.mechanics) == 1
    # Both halves: the player watched the lead-up and the outcome, so the recorded turn
    # is both. The tag itself is stripped.
    assert result.narration == (
        "You wedge your fingers under the gate.\n\n"
        "The iron shifts an inch, then slams back down."
    )
    assert "[[CHECK" not in result.narration


def test_the_second_call_gets_the_first_narration_back():
    """Otherwise the GM restages an attempt it already described and the player reads
    the same moment twice."""
    backend = MockBackend([
        "You wedge your fingers under the gate.\n\n[[CHECK: Strength DC 15 — it holds]]",
        "The iron shifts an inch, then slams back down.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7))
    engine.run("I force the portcullis.", player="Kelly", sheet=sheet())

    messages = backend.calls[1].messages
    assert messages[-2].role is Role.ASSISTANT
    assert "You wedge your fingers under the gate." in messages[-2].content
    assert "[[CHECK" not in messages[-2].content
    assert "do not restate" in messages[-1].content.lower()


def test_the_gm_is_never_handed_a_number(capsys):
    """OD-11, structurally: the second call's prompt must contain no engine values."""
    backend = MockBackend([
        "[[CHECK: Strength DC 15 — it holds]]",
        "It does not move.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7))
    engine.run("I force the portcullis.", player="Kelly", sheet=sheet())

    second_prompt = backend.calls[1].messages[-1].content
    mechanical = engine.campaign  # noqa: F841 - readability
    assert "succeeded" in second_prompt or "failed" in second_prompt
    # The roll total, the DC, and the modifier must not appear anywhere in the prompt.
    for forbidden in ("DC 15", "vs 15", "+3"):
        assert forbidden not in second_prompt


def test_the_mechanics_carry_the_numbers_instead():
    backend = MockBackend([
        "[[CHECK: Strength DC 15 — it holds]]",
        "It does not move.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7))
    result = engine.run("I force it.", player="Kelly", sheet=sheet())

    mechanical = result.mechanics[0]
    assert mechanical.dc == 15
    assert mechanical.total == mechanical.faces[0] + mechanical.modifier
    assert "DC 15" in mechanical.render()


def test_the_check_resolves_against_the_real_sheet():
    """A proficient athlete must roll with proficiency, not a default +0."""
    backend = MockBackend([
        "[[CHECK: Athletics DC 15 — it holds]]",
        "You heave.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(3))
    result = engine.run("I climb.", player="Kelly", sheet=sheet())

    # STR 16 (+3) and proficiency at level 2 (+2) = +5.
    assert result.mechanics[0].modifier == 5


def test_a_malformed_request_degrades_to_narration():
    """A bad tag must not end the evening — the turn still lands."""
    backend = MockBackend(["You try.\n\n[[CHECK: Vibes DC ninety]]"])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(1))

    result = engine.run("I try something.", player="Kelly", sheet=sheet())

    assert len(backend.calls) == 1
    assert result.mechanics == []


def test_the_loop_is_bounded():
    """A GM that keeps asking for rolls is a prompt bug, not a reason to spend money."""
    backend = MockBackend(["[[CHECK: Strength DC 10 — nothing]]"], repeat_last=True)
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(1))

    engine.run("I try.", player="Kelly", sheet=sheet())

    assert len(backend.calls) == MAX_GM_CALLS


def test_a_refusal_ends_the_turn_without_resolving():
    backend = MockBackend([GMResponse(text="", model="m", refused=True, refusal_category="x")])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(1))

    result = engine.run("something objectionable", player="Kelly", sheet=sheet())

    assert result.refused is True
    assert len(backend.calls) == 1


def test_the_turn_is_recorded_in_the_window():
    backend = MockBackend(["The hall is silent."])
    campaign = campaign_with()
    engine = TurnEngine(backend, campaign, rng=random.Random(1))

    engine.run("I listen.", player="Kelly", sheet=sheet())

    assert len(campaign.history) == 1
    assert campaign.history[0].speaker == "Kelly (Brannoc)"


def test_rolls_replay_from_the_seed():
    def run_once():
        backend = MockBackend([
            "[[CHECK: Strength DC 15 — it holds]]",
            "It does not move.",
        ])
        engine = TurnEngine(backend, campaign_with(), rng=random.Random(99))
        return engine.run("I force it.", player="Kelly", sheet=sheet()).mechanics[0]

    first, second = run_once(), run_once()
    assert first.seed == second.seed
    assert first.faces == second.faces


# --- logging ---------------------------------------------------------------


def test_the_event_stream_records_the_whole_turn(tmp_path):
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    backend = MockBackend([
        "[[CHECK: Strength DC 15 — it holds]]",
        "The iron does not move.",
    ])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7), log=log)
    engine.run("I force the portcullis.", player="Kelly", sheet=sheet())

    kinds = [event.type for event in read_log(log.path)]
    assert EventType.PLAYER_INPUT in kinds
    assert EventType.RULES_RESOLUTION in kinds
    assert EventType.GM_ADJUDICATION in kinds
    assert EventType.GM_NARRATION in kinds
    assert EventType.COST in kinds


def test_the_adjudication_links_to_the_resolution_it_governed(tmp_path):
    """D-008: the pair is what Phase 7 reads to ask whether a ruling was fair."""
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    backend = MockBackend(["[[CHECK: Strength DC 15 — it holds]]", "No luck."])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7), log=log)
    engine.run("I force it.", player="Kelly", sheet=sheet())

    events = list(read_log(log.path))
    adjudication = next(e for e in events if e.type is EventType.GM_ADJUDICATION)
    resolution = next(e for e in events if e.type is EventType.RULES_RESOLUTION)
    assert adjudication.resolution_seq == resolution.seq


def test_a_model_call_logs_pending_then_complete_sharing_a_call_id(tmp_path):
    """OD-9: the id has to exist before the response does, or the pair cannot be made."""
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    backend = MockBackend(["The hall is silent."])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(1), log=log)
    engine.run("I listen.", player="Kelly", sheet=sheet())

    narrations = [e for e in read_log(log.path) if e.type is EventType.GM_NARRATION]
    assert [e.status.value for e in narrations] == ["pending", "complete"]
    assert narrations[0].call_id == narrations[1].call_id
    assert narrations[0].call_id


def test_a_crashed_call_still_gets_a_terminal_row(tmp_path):
    """Otherwise a crash is indistinguishable from a call still in flight."""
    from dndc.logging import SessionLog

    class Exploding(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("connection reset")

    log = SessionLog.open(tmp_path)
    engine = TurnEngine(Exploding(), campaign_with(), rng=random.Random(1), log=log)

    with pytest.raises(GMBackendError):
        engine.run("I listen.", player="Kelly", sheet=sheet())

    narrations = [e for e in read_log(log.path) if e.type is EventType.GM_NARRATION]
    assert [e.status.value for e in narrations] == ["pending", "failed"]
    assert narrations[0].call_id == narrations[1].call_id


def test_the_resolution_records_faces_and_seed(tmp_path):
    """A logged session must replay exactly (D-008)."""
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    backend = MockBackend(["[[CHECK: Strength DC 15 — it holds]]", "No luck."])
    engine = TurnEngine(backend, campaign_with(), rng=random.Random(7), log=log)
    result = engine.run("I force it.", player="Kelly", sheet=sheet())

    resolution = next(e for e in read_log(log.path) if e.type is EventType.RULES_RESOLUTION)
    assert resolution.seed == result.mechanics[0].seed
    assert tuple(resolution.roll.rolls) == result.mechanics[0].faces

    replayed = resolve_check(
        random.Random(resolution.seed),
        ability_score=16, dc=15, level=2, proficiency=Proficiency.NONE, ability="str",
    )
    assert tuple(replayed.roll.rolls) == tuple(resolution.roll.rolls)


# --- the opening scene (P1.5 playtest finding) -----------------------------


def test_the_gm_opens_the_scene_before_anyone_speaks():
    """At a table the GM speaks first; the loop used to sit waiting for the player."""
    engine = _engine(["Rain hammers the shutters of the Grey Hollow."])
    result = engine.open_scene()

    assert "Rain hammers" in result.narration
    assert engine.campaign.history[0].opening is True


def test_the_opening_emits_no_player_input_because_nobody_spoke(tmp_path):
    from dndc.logging import SessionLog

    log = SessionLog.open(tmp_path)
    engine = _engine(["The road opens ahead."], log=log)
    engine.open_scene()

    types = [e.type.value for e in read_log(log.path)]
    assert "player_input" not in types
    assert types.count("gm_narration") == 2  # pending + complete


def test_the_opening_never_asks_for_a_check():
    """Nothing has been attempted yet, so a request is stripped rather than resolved."""
    engine = _engine(["You arrive at dusk.\n\n[[CHECK: Perception DC 12 — you miss it]]"])
    result = engine.open_scene()

    assert "CHECK" not in result.narration
    assert result.mechanics == []
    assert result.adjudication is None


def test_the_opening_is_not_attributed_to_a_player_in_the_window():
    engine = _engine(["The hall is cold."])
    engine.open_scene()

    (prompt, narration) = engine.campaign.window()
    assert prompt.content == "(the session opens)"
    assert narration.content == "The hall is cold."


def test_the_opening_uses_its_own_instruction():
    engine = _engine(["Somewhere to begin."])
    engine.open_scene()

    request = engine.backend.calls[-1]
    assert "nobody has spoken yet" in request.messages[-1].content
    assert "Do not ask for a check" in request.messages[-1].content
