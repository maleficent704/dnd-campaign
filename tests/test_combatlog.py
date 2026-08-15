"""P3.3 — the combat event vocabulary, and a fight that writes itself down.

D-008 was amended on 2026-08-15, *after* P3.1 and P3.2 existed rather than alongside
them, so the vocabulary would describe a fight rather than a guess at one. These tests
are how that claim is checked: a real encounter is played, logged, read back, and asked
the questions Phase 7 will ask of it.

The load-bearing assertions are about what the log makes *answerable*:

* a fight can be reconstructed — rolled monster hit points included, which is why
  `combat_start` carries the roster as instantiated;
* damage and the roll that caused it are separable, and linked;
* the D-008 families that already existed were reused rather than duplicated — attacks,
  death saves and initiative are `rules_resolution`, as its `kind` field said in 2026-07.
"""

from __future__ import annotations

import random

from dndc.game.combatlog import ATTACK, DEATH_SAVE, CombatRecorder, damage_taken
from dndc.logging import SessionLog, read_log
from dndc.rules.checks import resolve_attack
from dndc.rules.combat import Combatant, Encounter, Side, heal
from dndc.rules.statblock import from_monster
from dndc.schema.events import CombatOutcome, DamageEffect, EventType
from dndc.srd.repository import SRDRepository

import pytest


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


def pc(name: str = "Corin Vale", hp: int = 20, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(),
        name=name,
        side=Side.PARTY,
        max_hp=hp,
        current_hp=hp,
        armor_class=14,
        initiative_modifier=3,
        is_player=True,
    )
    data.update(overrides)
    return Combatant(**data)


def foe(name: str = "Wolf", hp: int = 11, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(),
        name=name,
        side=Side.FOES,
        max_hp=hp,
        current_hp=hp,
        armor_class=13,
        initiative_modifier=2,
    )
    data.update(overrides)
    return Combatant(**data)


def recorded(tmp_path, *combatants, seed: int = 5):
    """An encounter with a recorder attached, and the log they write to."""
    log = SessionLog.open(tmp_path)
    encounter = Encounter.start(random.Random(seed), list(combatants) or [pc(), foe()])
    recorder = CombatRecorder("fight-1", log)
    recorder.started(encounter, seed=seed)
    return encounter, recorder, log


def events_of(log, kind: EventType):
    return [e for e in read_log(log.path) if e.type is kind]


# --- combat_start -----------------------------------------------------------


def test_the_roster_is_logged_as_instantiated(tmp_path, repo):
    """Monster hit points may be rolled, so without this row every later event in the
    fight refers to a creature of unknown durability."""
    wolf = from_monster(repo.monster("wolf"), rng=random.Random(3)).combatant
    _, _, log = recorded(tmp_path, pc(), wolf)

    (start,) = events_of(log, EventType.COMBAT_START)
    recorded_wolf = next(c for c in start.combatants if c.id == wolf.id)
    assert recorded_wolf.max_hp == wolf.max_hp
    assert recorded_wolf.side.value == "foes" and not recorded_wolf.is_player


def test_the_initiative_order_is_logged(tmp_path):
    encounter, _, log = recorded(tmp_path)
    (start,) = events_of(log, EventType.COMBAT_START)
    assert list(start.order) == encounter.order


def test_the_seed_is_logged_so_the_fight_can_be_replayed(tmp_path):
    _, _, log = recorded(tmp_path, seed=99)
    (start,) = events_of(log, EventType.COMBAT_START)
    assert start.seed == 99


# --- one hit, two rows ------------------------------------------------------


def test_an_attack_and_its_damage_are_separate_linked_rows(tmp_path):
    """They come apart in real play — a fall damages with no attack roll, and resistance
    changes what a roll means without changing the roll."""
    encounter, recorder, log = recorded(tmp_path)
    rng = random.Random(1)
    target = encounter.get("wolf")
    result = resolve_attack(rng, attack_modifier=20, target_ac=1, damage_expression="1d6+2")
    seq = recorder.attack(encounter.get("corin"), target, result, seed=1)
    outcome = encounter.damage("wolf", result.damage, "slashing")
    recorder.hit_points(target, outcome, resolution_seq=seq)

    (attack,) = [e for e in events_of(log, EventType.RULES_RESOLUTION) if e.kind == ATTACK]
    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)

    assert attack.target == "wolf" and attack.dc == 1 and attack.success
    assert change.resolution_seq == attack.seq
    assert change.before == 11 and change.after == 11 - result.damage


def test_an_attack_needs_no_new_family(tmp_path):
    """`rules_resolution.kind` named `attack` in the original D-008 (2026-07-27). Combat
    reuses the vocabulary rather than growing it."""
    encounter, recorder, log = recorded(tmp_path)
    result = resolve_attack(random.Random(2), attack_modifier=5, target_ac=13)
    recorder.attack(encounter.get("corin"), encounter.get("wolf"), result)

    assert events_of(log, EventType.RULES_RESOLUTION)[0].kind == ATTACK


def test_the_damage_row_records_what_resistance_did(tmp_path):
    """The roll is unchanged by resistance; what it meant is not. That is the whole
    reason these are two rows."""
    encounter, recorder, log = recorded(
        tmp_path, pc(), foe(resistances=frozenset({"fire"}))
    )
    before = encounter.get("wolf")
    outcome = encounter.damage("wolf", 8, "fire")
    recorder.hit_points(before, outcome)

    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)
    assert change.effect is DamageEffect.RESISTANT
    assert change.amount == 4 and change.damage_type == "fire"


def test_temporary_hit_points_are_visible_in_the_row(tmp_path):
    encounter, recorder, log = recorded(tmp_path, pc(temporary_hp=5), foe())
    before = encounter.get("corin")
    outcome = encounter.damage("corin", 8)
    recorder.hit_points(before, outcome)

    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)
    assert change.temporary_absorbed == 5 and change.amount == 3


def test_dropping_and_dying_are_flagged_on_the_row(tmp_path):
    encounter, recorder, log = recorded(tmp_path)
    before = encounter.get("wolf")
    outcome = encounter.damage("wolf", 99)
    recorder.hit_points(before, outcome)

    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)
    assert change.dropped and change.killed


def test_healing_is_the_same_row_with_a_negative_amount(tmp_path):
    """So summing `amount` over a fight gives net damage without a caller knowing two
    shapes."""
    encounter, recorder, log = recorded(tmp_path)
    encounter.damage("corin", 10)
    before = encounter.get("corin")
    after = encounter.replace_combatant(heal(before, 6))
    recorder.healed(before, after)

    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)
    assert change.amount == -6 and change.after == before.current_hp + 6


# --- death saves ------------------------------------------------------------


def test_a_death_save_is_a_save_against_dc_ten(tmp_path):
    """Which is exactly what the rules say it is, so it needs no family of its own."""
    encounter, recorder, log = recorded(tmp_path)
    encounter.damage("corin", 99)
    result = encounter.death_save("corin", random.Random(4))
    recorder.death_save(encounter.get("corin"), result)

    (save,) = [e for e in events_of(log, EventType.RULES_RESOLUTION) if e.kind == DEATH_SAVE]
    assert save.dc == 10 and save.ability is None
    assert save.actor == "corin"


def test_the_death_save_row_carries_the_running_tally(tmp_path):
    """The roll is one thing; how close to dead it left them is another, and a reader
    should not have to count backwards through the log."""
    encounter, recorder, log = recorded(tmp_path)
    encounter.damage("corin", 99)
    for _ in range(2):
        result = encounter.death_save("corin", random.Random(0))
        recorder.death_save(encounter.get("corin"), result)

    saves = [e for e in events_of(log, EventType.RULES_RESOLUTION) if e.kind == DEATH_SAVE]
    tallies = [e.detail["successes"] + e.detail["failures"] for e in saves]
    assert tallies == [1, 2]


# --- turns and the end ------------------------------------------------------


def test_each_turn_is_a_row(tmp_path):
    """Derivable in principle from the order; derivable-in-principle is where analysis
    goes wrong, and Phase 7 will ask which round a narration happened in."""
    encounter, recorder, log = recorded(tmp_path)
    recorder.turn(encounter)
    encounter.advance()
    recorder.turn(encounter)

    turns = events_of(log, EventType.COMBAT_TURN)
    assert [t.combatant for t in turns] == encounter.order[:2]
    assert all(t.round == 1 for t in turns)


def test_the_end_records_outcome_length_and_survivors(tmp_path):
    encounter, recorder, log = recorded(tmp_path)
    encounter.damage("wolf", 99)
    recorder.ended(encounter)

    (end,) = events_of(log, EventType.COMBAT_END)
    assert end.outcome is CombatOutcome.PARTY
    assert end.rounds == 1 and end.survivors == ("corin",)


def test_everyone_down_is_a_draw(tmp_path):
    encounter, recorder, log = recorded(tmp_path)
    encounter.damage("wolf", 99)
    encounter.damage("corin", 99)
    recorder.ended(encounter)

    (end,) = events_of(log, EventType.COMBAT_END)
    assert end.outcome is CombatOutcome.DRAW and end.survivors == ()


# --- no log, no problem -----------------------------------------------------


def test_a_recorder_without_a_log_is_a_no_op(tmp_path):
    """So a fight runs in a scratch script or a rules test without a session."""
    encounter = Encounter.start(random.Random(1), [pc(), foe()])
    recorder = CombatRecorder("fight-1")
    assert recorder.started(encounter) is None
    assert recorder.turn(encounter) is None
    assert recorder.ended(encounter) is None


# --- the whole fight, read back ---------------------------------------------


def test_a_logged_fight_answers_the_questions_it_was_designed_for(tmp_path, repo):
    """The point of the amendment. Play a real fight, then ask the log what happened —
    without simulating it again."""
    rng = random.Random(11)
    corin = pc(hp=24)
    wolves = [
        from_monster(repo.monster("wolf"), combatant_id=f"wolf-{n}", name=f"Wolf {n}")
        for n in (1, 2)
    ]
    log = SessionLog.open(tmp_path)
    encounter = Encounter.start(rng, [corin, *(w.combatant for w in wolves)])
    recorder = CombatRecorder("mill-yard", log)
    recorder.started(encounter, seed=11)

    guard = 0
    while not encounter.over and guard < 60:
        guard += 1
        recorder.turn(encounter)
        actor = encounter.active
        if actor.dying:
            recorder.death_save(actor, encounter.death_save(actor.id, rng))
        elif actor.acts:
            target = next(
                (c for c in encounter.combatants.values()
                 if c.side is not actor.side and not c.down),
                None,
            )
            if target is not None:
                attack = wolves[0].attacks[0]
                result = resolve_attack(
                    rng,
                    attack_modifier=attack.attack_bonus if not actor.is_player else 5,
                    target_ac=target.armor_class,
                    damage_expression=attack.damage_expression if not actor.is_player else "1d8+3",
                )
                seq = recorder.attack(actor, target, result)
                if result.hit:
                    before = target
                    outcome = encounter.damage(target.id, result.damage, attack.damage_type)
                    recorder.hit_points(before, outcome, resolution_seq=seq)
        encounter.advance()
    recorder.ended(encounter)

    events = list(read_log(log.path))
    starts = [e for e in events if e.type is EventType.COMBAT_START]
    ends = [e for e in events if e.type is EventType.COMBAT_END]
    changes = [e for e in events if e.type is EventType.HIT_POINT_CHANGE]

    # The fight has a beginning and an end, and the roster is reconstructable from the log
    # alone — no repository, no seed replay.
    assert len(starts) == 1 and len(ends) == 1
    assert {c.id for c in starts[0].combatants} == set(encounter.combatants)

    # Every damage row points at a real combatant and at the roll that caused it.
    assert changes, "a fight with no damage is not a fight"
    for change in changes:
        assert change.combatant in encounter.combatants
        assert change.resolution_seq is not None
        assert change.before != change.after

    # And the numbers agree with the final state, without re-simulating anything.
    for combatant_id, total in damage_taken(changes).items():
        final = encounter.get(combatant_id)
        assert final.current_hp == final.max_hp - total

    assert ends[0].rounds >= 1
    assert ends[0].outcome in (CombatOutcome.PARTY, CombatOutcome.FOES, CombatOutcome.DRAW)


def test_a_damage_row_agrees_with_itself(tmp_path):
    """`before - amount == after`, always. Damage is floored at zero, so the raw figure
    can exceed what came off; a row disagreeing with its own numbers is worse than a
    missing one, and this is the invariant every sum over the log depends on."""
    encounter, recorder, log = recorded(tmp_path, pc(hp=6), foe())
    before = encounter.get("corin")
    outcome = encounter.damage("corin", 40)
    recorder.hit_points(before, outcome)

    (change,) = events_of(log, EventType.HIT_POINT_CHANGE)
    assert change.before - change.amount == change.after
    assert change.amount == 6
