"""P3.7 — monster tactics become the GM's, per Fable's 2026-08-15 (c) ruling.

Target selection is categorical judgment — "who does the goblin attack" needs no numbers —
so it belongs on the GM's side of D-001 under OD-12's own test. What had kept it in the
engine was replayability, and that was already solved: a logged target choice is no
different from a logged DC, and replay reads the judgment back instead of re-asking.

What is defended here:

* the declaration is honoured when it still makes sense, and **never silently replaced**
  when it does not — `stale` and `policy` are different findings and both are logged;
* a fight never stalls on a missing or unreadable tag;
* the tag never reaches a player's screen, and never re-enters the GM's own window.
"""

from __future__ import annotations

import random

from dndc.game.combatlog import CombatRecorder
from dndc.game.combatturn import CombatEngine
from dndc.gm.targettag import find_target_declarations, strip_target_declarations
from dndc.logging import SessionLog, read_log
from dndc.models.mock import MockBackend
from dndc.rules.combat import Combatant, Encounter, Side
from dndc.rules.statblock import Attack, StatBlock
from dndc.schema.events import EventType, TargetSource


def pc(name: str = "Corin Vale", hp: int = 24, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(), name=name, side=Side.PARTY, max_hp=hp,
        current_hp=hp, armor_class=14, initiative_modifier=3, is_player=True,
    )
    data.update(overrides)
    return Combatant(**data)


def foe(name: str = "Wolf", hp: int = 11, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower().replace(" ", "-"), name=name, side=Side.FOES,
        max_hp=hp, current_hp=hp, armor_class=13, initiative_modifier=2,
    )
    data.update(overrides)
    return Combatant(**data)


def block(combatant: Combatant) -> StatBlock:
    return StatBlock(
        combatant=combatant,
        attacks=(Attack(name="Bite", attack_bonus=20, damage_expression="1d4",
                        damage_type="piercing"),),
    )


def engine(*combatants, seed: int = 3, backend=None, log=None) -> CombatEngine:
    people = list(combatants)
    encounter = Encounter.start(random.Random(seed), people)
    return CombatEngine(
        encounter,
        backend=backend,
        recorder=CombatRecorder("fight", log),
        blocks={c.id: block(c) for c in people if not c.is_player},
        rng=random.Random(seed),
    )


# --- the tag ------------------------------------------------------------------


def test_a_declaration_names_an_attacker_and_a_victim():
    (found,) = find_target_declarations("[[TARGET: Wolf 2 -> Brother Hammond]]")
    assert found.actor == "Wolf 2" and found.target == "Brother Hammond"


def test_several_declarations_in_one_reply_all_parse():
    found = find_target_declarations(
        "The pack splits. [[TARGET: Wolf 1 -> Corin]] [[TARGET: Wolf 2 -> Hammond]]"
    )
    assert [(f.actor, f.target) for f in found] == [("Wolf 1", "Corin"), ("Wolf 2", "Hammond")]


def test_the_arrow_is_forgiving():
    """The producer is a language model and rejecting a turn over an en dash would be a
    bad trade."""
    for arrow in ("->", "→", "—", "=>"):
        (found,) = find_target_declarations(f"[[TARGET: Wolf {arrow} Corin]]")
        assert found.target == "Corin"


def test_a_declaration_missing_half_of_itself_is_dropped():
    """Guessing the victim is precisely the judgment the tag exists to hand over."""
    assert find_target_declarations("[[TARGET: Wolf 1]]") == []
    assert find_target_declarations("[[TARGET: -> Corin]]") == []


def test_the_tag_never_reaches_the_screen():
    text = "The wolf circles. [[TARGET: Wolf 1 -> Corin]] Its hackles rise."
    assert strip_target_declarations(text) == "The wolf circles. Its hackles rise."


def test_stripping_closes_the_gap_the_tag_left():
    assert "  " not in strip_target_declarations("It circles. [[TARGET: A -> B]] It waits.")


# --- honouring the declaration ------------------------------------------------


def test_a_declared_target_is_honoured():
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe())
    subject.record_declarations("[[TARGET: Wolf -> Brother Hammond]]")

    target, source = subject.resolve_target(subject.encounter.get("wolf"))
    assert target.id == "brother" and source is TargetSource.DECLARED


def test_a_declaration_overrides_the_policy():
    """The policy would take the most wounded; the GM said otherwise, and the GM wins."""
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe())
    subject.encounter.damage("corin", 10)
    subject.record_declarations("[[TARGET: Wolf -> Brother Hammond]]")

    target, source = subject.resolve_target(subject.encounter.get("wolf"))
    assert target.id == "brother" and source is TargetSource.DECLARED


def test_no_declaration_falls_back_to_policy_and_says_so():
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe())
    subject.encounter.damage("corin", 10)

    target, source = subject.resolve_target(subject.encounter.get("wolf"))
    assert target.id == "corin" and source is TargetSource.POLICY


def test_a_declaration_overtaken_by_events_is_stale_not_silently_replaced():
    """Declarations are written a turn ahead. "The GM chose badly" and "the GM's choice
    expired" are different findings."""
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe())
    subject.record_declarations("[[TARGET: Wolf -> Brother Hammond]]")
    subject.encounter.damage("brother", 99)

    target, source = subject.resolve_target(subject.encounter.get("wolf"))
    assert source is TargetSource.STALE and target.id == "corin"


def test_a_declaration_naming_nobody_in_the_fight_is_dropped_on_arrival():
    """Dropped now rather than becoming a stale declaration later."""
    subject = engine(pc(), foe())
    assert subject.record_declarations("[[TARGET: Dragon -> Corin Vale]]") == 0
    assert subject.declared == {}


def test_a_declaration_is_for_one_turn_not_a_standing_order():
    """A standing order would go stale silently, which is the failure this whole ruling
    is designed to make visible."""
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe())
    subject.record_declarations("[[TARGET: Wolf -> Brother Hammond]]")

    first = subject.resolve_target(subject.encounter.get("wolf"))
    second = subject.resolve_target(subject.encounter.get("wolf"))
    assert first[1] is TargetSource.DECLARED
    assert second[1] is TargetSource.POLICY


def test_declarations_are_matched_with_the_same_tiered_matcher_as_switch():
    """"Wolf" for "Wolf 1", "Hammond" for "Brother Hammond"."""
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe("Wolf 1"))
    subject.record_declarations("[[TARGET: Wolf -> Hammond]]")

    target, source = subject.resolve_target(subject.encounter.get("wolf"))
    assert source is TargetSource.DECLARED and target.name == "Brother Hammond"


# --- the loop and the log -----------------------------------------------------


def test_a_turn_logs_who_it_attacked_and_who_decided(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = engine(pc(), foe(), log=log)
    while subject.encounter.active.id != "wolf":
        subject.advance()
    subject.record_declarations("[[TARGET: Wolf -> Corin Vale]]")

    subject.take_turn()

    (turn,) = [e for e in read_log(log.path) if e.type is EventType.COMBAT_TURN]
    assert turn.target == "corin" and turn.target_source is TargetSource.DECLARED


def test_a_policy_fallback_is_logged_as_a_fallback(tmp_path):
    """Phase 7 must never have to guess whether a choice was made or defaulted."""
    log = SessionLog.open(tmp_path)
    subject = engine(pc(), foe(), log=log)
    while subject.encounter.active.id != "wolf":
        subject.advance()

    subject.take_turn()

    (turn,) = [e for e in read_log(log.path) if e.type is EventType.COMBAT_TURN]
    assert turn.target_source is TargetSource.POLICY


def test_the_gm_declaring_in_its_narration_reaches_the_engine():
    """Zero extra calls was a condition of the ruling: the declaration rides on the
    narration the GM was already making."""
    backend = MockBackend(["It lunges. [[TARGET: Wolf -> Brother Hammond]]"])
    subject = engine(pc("Corin Vale"), pc("Brother Hammond"), foe(), backend=backend)
    while subject.encounter.active.id != "wolf":
        subject.advance()

    outcome = subject.take_turn()

    assert subject.declared == {"wolf": "Brother Hammond"}
    assert "[[TARGET" not in outcome.narration


def test_a_refused_narration_declares_nothing():
    from dndc.models.base import GMResponse, Usage

    refusal = GMResponse(
        text="[[TARGET: Wolf -> Corin Vale]]", model="m",
        usage=Usage(input_tokens=1, output_tokens=1), refused=True,
    )
    subject = engine(pc(), foe(), backend=MockBackend([refusal]))
    while subject.encounter.active.id != "wolf":
        subject.advance()
    subject.take_turn()

    assert subject.declared == {}
