"""P3.4 — the combat turn loop, and D-001's boundary under its heaviest load.

The load-bearing assertions are boundary assertions, as they were in P1.3:

* **the GM is never handed a number** — it receives severity words computed against the
  target's own maximum, which is OD-12's structural ban rather than an instruction a model
  has to keep remembering;
* **the fight is decided and logged before a model sees any of it**, so a narration cannot
  change an outcome and a session that loses its GM mid-fight still has a correct combat
  log;
* **monster tactics are deterministic**, because a fight that cannot be replayed from its
  seed is not evidence of anything;
* **an unresolved multiattack is never quietly one attack** — the wrong answer that looks
  like a right one.
"""

from __future__ import annotations

import random

import pytest

from dndc.game.combatlog import CombatRecorder
from dndc.game.combatturn import (
    AttackPlan,
    CombatEngine,
    PlannedAttack,
    choose_target,
    plan_attacks,
    run_round,
)
from dndc.logging import SessionLog, read_log
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.rules.combat import Combatant, Encounter, Side
from dndc.rules.statblock import Attack, Multiattack, StatBlock, from_monster
from dndc.schema.events import CallStatus, EventType
from dndc.srd.repository import SRDRepository


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


def pc(name: str = "Corin Vale", hp: int = 24, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(), name=name, side=Side.PARTY, max_hp=hp,
        current_hp=hp, armor_class=14, initiative_modifier=3, is_player=True,
    )
    data.update(overrides)
    return Combatant(**data)


def foe(name: str = "Wolf", hp: int = 11, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(), name=name, side=Side.FOES, max_hp=hp,
        current_hp=hp, armor_class=13, initiative_modifier=2,
    )
    data.update(overrides)
    return Combatant(**data)


def block(combatant: Combatant, *, multiattack: Multiattack | None = None, **attack) -> StatBlock:
    data = dict(name="Bite", attack_bonus=20, damage_expression="1d6+2", damage_type="piercing")
    data.update(attack)
    return StatBlock(
        combatant=combatant, attacks=(Attack(**data),), multiattack=multiattack
    )


def engine(*combatants, seed: int = 3, backend=None, log=None, blocks=None) -> CombatEngine:
    people = list(combatants) or [pc(), foe()]
    encounter = Encounter.start(random.Random(seed), people)
    return CombatEngine(
        encounter,
        backend=backend,
        recorder=CombatRecorder("fight", log),
        blocks=blocks or {},
        rng=random.Random(seed),
    )


# --- the number ban (OD-12) --------------------------------------------------


def test_the_gm_is_handed_severity_words_and_no_numbers():
    """The structural ban: a model cannot restate a value it was never given."""
    backend = MockBackend(["The wolf's teeth find his shoulder."])
    wolf = foe()
    subject = engine(pc(), wolf, backend=backend, blocks={"wolf": block(wolf)})
    while subject.encounter.active.id != "wolf":
        subject.advance()

    outcome = subject.take_turn()

    # What the engine says about the fight, which is the only fight-shaped thing the
    # model receives. (The template's own prose has digits in it — "40-90 words" — so
    # scanning the whole message would test the instructions, not the boundary.)
    assert outcome.severities
    for line in outcome.severities:
        assert not any(character.isdigit() for character in line), line

    (request,) = backend.calls
    sent = request.messages[-1].content
    assert all(line in sent for line in outcome.severities)


def test_severity_is_measured_against_the_targets_own_maximum():
    """Six damage is a scratch to a barbarian and nearly lethal to a level-1 wizard, and
    the felt sense should track the second reading."""
    wolf = foe()
    frail = engine(pc(hp=8), wolf, blocks={"wolf": block(wolf, damage_expression="6")})
    while frail.encounter.active.id != "wolf":
        frail.advance()
    weak = frail.take_turn().severities[0]

    wolf2 = foe()
    tough = engine(pc(hp=80), wolf2, blocks={"wolf": block(wolf2, damage_expression="6")})
    while tough.encounter.active.id != "wolf":
        tough.advance()
    strong = tough.take_turn().severities[0]

    assert weak != strong


def test_a_miss_is_reported_as_a_miss():
    wolf = foe()
    subject = engine(pc(), wolf, blocks={"wolf": block(wolf, attack_bonus=-40)})
    while subject.encounter.active.id != "wolf":
        subject.advance()
    assert "misses" in subject.take_turn().severities[0]


# --- resolve first, narrate second -------------------------------------------


def test_the_fight_is_resolved_and_logged_before_the_model_is_called(tmp_path):
    """A narration cannot change an outcome, and a session that loses its GM mid-fight
    still has a complete and correct combat log."""
    class _Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("the model went away")

    log = SessionLog.open(tmp_path)
    wolf = foe()
    subject = engine(pc(), wolf, backend=_Dead(), log=log, blocks={"wolf": block(wolf)})
    while subject.encounter.active.id != "wolf":
        subject.advance()

    with pytest.raises(GMBackendError):
        subject.take_turn()

    # The damage happened, and it is on file.
    assert subject.encounter.get("corin").current_hp < 24
    changes = [e for e in read_log(log.path) if e.type is EventType.HIT_POINT_CHANGE]
    assert len(changes) == 1 and changes[0].combatant == "corin"


def test_a_failed_narration_still_writes_its_terminal_row(tmp_path):
    """OD-9's pending discipline: a crashed call must not be indistinguishable from one
    still in flight."""
    class _Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("the model went away")

    log = SessionLog.open(tmp_path)
    wolf = foe()
    subject = engine(pc(), wolf, backend=_Dead(), log=log, blocks={"wolf": block(wolf)})
    while subject.encounter.active.id != "wolf":
        subject.advance()
    with pytest.raises(GMBackendError):
        subject.take_turn()

    narrations = [e for e in read_log(log.path) if e.type is EventType.GM_NARRATION]
    assert [n.status for n in narrations] == [CallStatus.PENDING, CallStatus.FAILED]


def test_a_turn_that_did_nothing_narrates_nothing():
    """Silence is cheaper and more honest than "the wolf hesitates"."""
    backend = MockBackend(["should not be called"])
    subject = engine(pc(), foe(), backend=backend)
    subject.take_turn()
    assert backend.calls == []


def test_a_narration_is_logged_as_a_combat_scene(tmp_path):
    log = SessionLog.open(tmp_path)
    wolf = foe()
    subject = engine(
        pc(), wolf, backend=MockBackend(["Teeth close on his arm."]), log=log,
        blocks={"wolf": block(wolf)},
    )
    while subject.encounter.active.id != "wolf":
        subject.advance()
    subject.take_turn()

    complete = [
        e for e in read_log(log.path)
        if e.type is EventType.GM_NARRATION and e.status is CallStatus.COMPLETE
    ]
    assert complete and complete[0].scene == "combat"


# --- tactics ------------------------------------------------------------------


def test_the_engine_swings_at_the_most_wounded_enemy():
    """Deterministic and deliberately dull. A model choosing here would make the fight
    unreplayable, and replay-from-seed is what the combat core was built for."""
    encounter = Encounter.start(random.Random(1), [pc("Corin"), pc("Hammond"), foe()])
    encounter.damage("hammond", 10)
    assert choose_target(encounter, encounter.get("wolf")).id == "hammond"


def test_targeting_ignores_the_fallen():
    encounter = Encounter.start(random.Random(1), [pc("Corin"), pc("Hammond"), foe()])
    encounter.damage("hammond", 99)
    assert choose_target(encounter, encounter.get("wolf")).id == "corin"


def test_targeting_returns_nobody_when_the_other_side_is_down():
    encounter = Encounter.start(random.Random(1), [pc(), foe()])
    encounter.damage("corin", 99)
    assert choose_target(encounter, encounter.get("wolf")) is None


def test_the_same_seed_gives_the_same_fight():
    def play(seed: int) -> list[str]:
        wolf = foe()
        subject = engine(pc(), wolf, seed=seed, blocks={"wolf": block(wolf, attack_bonus=2)})
        lines = []
        for _ in range(4):
            if subject.encounter.over:
                break
            for outcome in run_round(subject):
                lines.extend(outcome.severities)
        return lines

    assert play(9) == play(9)


# --- multiattack --------------------------------------------------------------


def test_a_resolved_multiattack_becomes_that_many_swings():
    wolf = foe()
    statblock = StatBlock(
        combatant=wolf,
        attacks=(
            Attack(name="Bite", attack_bonus=5, damage_expression="1d6"),
            Attack(name="Claws", attack_bonus=5, damage_expression="1d4"),
        ),
        multiattack=Multiattack(
            raw="two attacks", count=2, parts=(("Bite", 1), ("Claws", 1)), resolved=True
        ),
    )
    plan = plan_attacks(statblock, "corin")
    assert [p.attack.name for p in plan.attacks] == ["Bite", "Claws"]
    assert not plan.approximated


def test_an_unresolved_multiattack_uses_its_stated_count_and_says_so():
    """The count in "makes three melee attacks" is a fact even when *which* attacks is
    not, and using it is far closer than dropping two swings on the floor."""
    wolf = foe()
    statblock = block(wolf, name="Scimitar")
    statblock = StatBlock(
        combatant=wolf,
        attacks=statblock.attacks,
        multiattack=Multiattack(raw="three melee attacks. Or two ranged.", count=3),
    )
    plan = plan_attacks(statblock, "corin")

    assert len(plan.attacks) == 3
    assert plan.approximated and "Or two ranged" in plan.note


def test_an_unresolved_multiattack_with_no_count_is_one_swing_and_says_so():
    """Never silently one. The wrong answer that looks like a right one."""
    wolf = foe()
    statblock = StatBlock(
        combatant=wolf,
        attacks=block(wolf).attacks,
        multiattack=Multiattack(raw="does something complicated"),
    )
    plan = plan_attacks(statblock, "corin")
    assert len(plan.attacks) == 1 and plan.approximated


def test_a_stat_block_with_no_attacks_plans_nothing_and_explains():
    statblock = StatBlock(combatant=foe(), attacks=())
    plan = plan_attacks(statblock, "corin")
    assert plan.attacks == [] and "no usable attack" in plan.note


def test_the_approximation_reaches_the_turn_outcome():
    wolf = foe()
    statblock = StatBlock(
        combatant=wolf,
        attacks=block(wolf).attacks,
        multiattack=Multiattack(raw="three attacks or something", count=3),
    )
    subject = engine(pc(), wolf, blocks={"wolf": statblock})
    while subject.encounter.active.id != "wolf":
        subject.advance()

    outcome = subject.take_turn()
    assert outcome.approximated and outcome.note


def test_a_multiattack_stops_when_the_target_drops():
    """The engine does not swing at a corpse to use up a multiattack."""
    wolf = foe()
    statblock = StatBlock(
        combatant=wolf,
        attacks=(Attack(name="Bite", attack_bonus=40, damage_expression="100"),),
        multiattack=Multiattack(raw="three attacks", count=3),
    )
    subject = engine(pc(hp=10), wolf, blocks={"wolf": statblock})
    while subject.encounter.active.id != "wolf":
        subject.advance()

    assert len(subject.take_turn().attacks) == 1


# --- the loop -----------------------------------------------------------------


def test_a_dying_combatant_rolls_a_death_save_on_their_turn(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = engine(pc(), foe(), log=log)
    # Exactly to zero. 99 would be massive damage — instant death, no saves — and this
    # test wants the character dying rather than dead.
    subject.encounter.damage("corin", 24)
    while subject.encounter.active.id != "corin":
        subject.advance()

    subject.death_save()

    saves = [
        e for e in read_log(log.path)
        if e.type is EventType.RULES_RESOLUTION and e.kind == "save"
    ]
    assert len(saves) == 1 and saves[0].actor == "corin"


def test_a_round_gives_everyone_a_turn():
    wolf = foe()
    subject = engine(pc(), wolf, blocks={"wolf": block(wolf)})
    outcomes = run_round(subject)
    assert {o.actor for o in outcomes} == {"corin", "wolf"}


def test_a_round_stops_when_the_fight_does():
    wolf = foe()
    statblock = block(wolf, attack_bonus=40, damage_expression="100")
    subject = engine(pc(hp=5), wolf, blocks={"wolf": statblock})
    run_round(subject)
    assert subject.encounter.over


def test_a_player_supplies_their_own_plan():
    """Players choose their actions; the engine only picks for what it runs."""
    wolf = foe()
    subject = engine(pc(), wolf)
    while subject.encounter.active.id != "corin":
        subject.advance()

    plan = AttackPlan(attacks=[
        PlannedAttack(Attack(name="Rapier", attack_bonus=20, damage_expression="1d8+3"), "wolf")
    ])
    outcome = subject.take_turn(plan)

    assert outcome.acted and subject.encounter.get("wolf").current_hp < 11


# --- a whole fight, logged ----------------------------------------------------


def test_a_real_fight_runs_end_to_end_and_logs_itself(tmp_path, repo):
    log = SessionLog.open(tmp_path)
    wolves = [
        from_monster(repo.monster("wolf"), combatant_id=f"wolf-{n}", name=f"Wolf {n}")
        for n in (1, 2)
    ]
    encounter = Encounter.start(
        random.Random(5), [pc(hp=30), *(w.combatant for w in wolves)]
    )
    recorder = CombatRecorder("mill-yard", log)
    recorder.started(encounter, seed=5)
    subject = CombatEngine(
        encounter,
        recorder=recorder,
        blocks={w.combatant.id: w for w in wolves},
        rng=random.Random(5),
    )

    rounds = 0
    while not encounter.over and rounds < 25:
        rounds += 1
        run_round(
            subject,
            plan_for=lambda actor: AttackPlan(
                attacks=[PlannedAttack(
                    Attack(name="Rapier", attack_bonus=6, damage_expression="1d8+3"),
                    choose_target(encounter, actor).id,
                )]
            ) if actor.is_player and choose_target(encounter, actor) else None,
        )
    recorder.ended(encounter)

    events = list(read_log(log.path))
    assert [e.type for e in events].count(EventType.COMBAT_END) == 1
    assert any(e.type is EventType.HIT_POINT_CHANGE for e in events)
    assert encounter.over


def test_a_slain_monster_is_reported_as_killed_not_as_dying():
    """`damage_severity` says "unconscious and dying" for anything at zero, which is right
    for a character and wrong for a monster. Caught by the first live run, where a wolf on
    the floor was being handed to the GM as dying."""
    wolf = foe(hp=4)
    subject = engine(pc(), wolf)
    while subject.encounter.active.id != "corin":
        subject.advance()
    plan = AttackPlan(attacks=[
        PlannedAttack(Attack(name="Rapier", attack_bonus=40, damage_expression="6"), "wolf")
    ])

    (line,) = subject.take_turn(plan).severities
    assert "killed" in line and "dying" not in line


def test_a_dropped_character_is_still_reported_as_dying():
    wolf = foe()
    subject = engine(pc(hp=6), wolf, blocks={"wolf": block(wolf, damage_expression="6")})
    while subject.encounter.active.id != "wolf":
        subject.advance()

    (line,) = subject.take_turn().severities
    assert "dying" in line


def test_a_death_save_is_said_out_loud():
    """Silently is how the clock gets taken out of the tensest part of the game."""
    subject = engine(pc(), foe())
    subject.encounter.damage("corin", 24)
    while subject.encounter.active.id != "corin":
        subject.advance()

    outcome = subject.death_save()
    assert outcome.severities and not any(c.isdigit() for c in outcome.severities[0])
