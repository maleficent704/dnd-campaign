"""P3.1 — the deterministic combat core.

This is the phase D-001 was written for: every number in a fight is the engine's, and the
GM (arriving in P3.4) receives outcomes rather than inputs. So the tests here are all
mechanical, and there is no live run to do — nothing in `rules/combat.py` can reach a
model, which is the property worth having.

What is defended:

* a fight replays — same seed, same combatants, same order, ties included;
* 5e's rules where they are load-bearing and easy to get subtly wrong: resistance
  precedence, temporary hit points, the difference between a monster dropping and a
  character dying, death saves, massive damage;
* a dying character still gets a turn, because that turn is where the death save happens.
"""

from __future__ import annotations

import random

import pytest

from dndc.rules.combat import (
    DEATH_SAVES_NEEDED,
    CombatError,
    Combatant,
    Condition,
    DamageEffect,
    DeathSaves,
    Encounter,
    Side,
    TurnBudget,
    apply_damage,
    heal,
    record_death_save,
    roll_initiative,
)


def pc(name: str = "Corin Vale", hp: int = 12, **overrides) -> Combatant:
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


def dying(**overrides) -> Combatant:
    return pc(current_hp=0, conditions=frozenset({Condition.UNCONSCIOUS}), **overrides)


class _Dice(random.Random):
    """A d20 that rolls exactly what the test says, so a rule is tested and not luck."""

    def __init__(self, *values: int) -> None:
        super().__init__(0)
        self._values = list(values)

    def randint(self, a: int, b: int) -> int:  # noqa: D102 - stdlib signature
        return self._values.pop(0) if self._values else super().randint(a, b)


# --- damage -----------------------------------------------------------------


def test_damage_comes_off_hit_points():
    outcome = apply_damage(pc(hp=12), 5)
    assert outcome.taken == 5 and outcome.combatant.current_hp == 7


def test_resistance_halves_and_rounds_down():
    outcome = apply_damage(pc(resistances=frozenset({"fire"})), 7, "fire")
    assert outcome.effect is DamageEffect.RESISTANT and outcome.effective == 3


def test_vulnerability_doubles():
    outcome = apply_damage(pc(vulnerabilities=frozenset({"fire"})), 6, "fire")
    assert outcome.effect is DamageEffect.VULNERABLE and outcome.effective == 12


def test_immunity_beats_everything():
    """5e's precedence: immune wins outright, even alongside vulnerability."""
    target = pc(immunities=frozenset({"fire"}), vulnerabilities=frozenset({"fire"}))
    outcome = apply_damage(target, 9, "fire")
    assert outcome.effect is DamageEffect.IMMUNE and outcome.taken == 0


def test_resistance_and_vulnerability_cancel():
    """They do not stack in either direction — the result is plain damage."""
    target = pc(resistances=frozenset({"fire"}), vulnerabilities=frozenset({"fire"}))
    outcome = apply_damage(target, 8, "fire")
    assert outcome.effect is DamageEffect.NORMAL and outcome.effective == 8


def test_an_untyped_hit_is_never_resisted():
    outcome = apply_damage(pc(resistances=frozenset({"fire"})), 8)
    assert outcome.effective == 8


def test_temporary_hit_points_are_spent_first():
    outcome = apply_damage(pc(hp=12, temporary_hp=5), 8)
    assert outcome.absorbed == 5 and outcome.taken == 3
    assert outcome.combatant.current_hp == 9 and outcome.combatant.temporary_hp == 0


def test_temporary_hit_points_can_absorb_a_hit_entirely():
    outcome = apply_damage(pc(hp=12, temporary_hp=9), 6)
    assert outcome.taken == 0 and outcome.combatant.current_hp == 12
    assert outcome.combatant.temporary_hp == 3


def test_hit_points_never_go_below_zero():
    outcome = apply_damage(pc(hp=6), 40)
    assert outcome.combatant.current_hp == 0


# --- dropping, dying, dying properly ----------------------------------------


def test_a_monster_at_zero_is_dead():
    """Monsters drop. Only characters get the thirty seconds."""
    outcome = apply_damage(foe(hp=7), 7)
    assert outcome.killed and outcome.combatant.dead
    assert not outcome.combatant.dying


def test_a_character_at_zero_is_unconscious_and_dying():
    outcome = apply_damage(pc(hp=7), 7)
    assert not outcome.killed
    assert outcome.dropped and outcome.combatant.dying
    assert Condition.UNCONSCIOUS in outcome.combatant.conditions


def test_massive_damage_kills_a_character_outright():
    """Damage carrying past zero by the whole maximum. The one way to die without a
    single death save, which is why it lives here and not in a caller."""
    outcome = apply_damage(pc(hp=10), 20)
    assert outcome.massive and outcome.killed and outcome.combatant.dead


def test_damage_just_short_of_massive_only_drops():
    outcome = apply_damage(pc(hp=10), 19)
    assert not outcome.massive and outcome.combatant.dying


def test_hitting_a_dying_character_is_a_failed_death_save():
    outcome = apply_damage(dying(), 3)
    assert outcome.combatant.death_saves.failures == 1
    assert not outcome.combatant.dead


def test_three_hits_on_a_dying_character_kill_them():
    target = dying()
    for _ in range(DEATH_SAVES_NEEDED):
        target = apply_damage(target, 2).combatant
    assert target.dead


def test_a_hit_unstabilises_a_stable_character():
    stable = dying().with_conditions(add=(Condition.STABLE,))
    assert apply_damage(stable, 2).combatant.dying


# --- healing ----------------------------------------------------------------


def test_healing_wakes_a_dying_character_and_clears_the_tally():
    target = dying()
    target = apply_damage(target, 2).combatant
    healed = heal(target, 4)

    assert healed.current_hp == 4 and not healed.dying
    assert healed.death_saves == DeathSaves()
    assert Condition.UNCONSCIOUS not in healed.conditions


def test_healing_cannot_exceed_the_maximum():
    assert heal(pc(hp=12, current_hp=9), 99).current_hp == 12


def test_healing_cannot_raise_the_dead():
    corpse = apply_damage(foe(hp=5), 5).combatant
    assert heal(corpse, 10) == corpse


# --- death saves ------------------------------------------------------------


def test_a_ten_or_better_is_a_success():
    result = record_death_save(_Dice(12), dying())
    assert result.success and result.combatant.death_saves.successes == 1


def test_a_nine_or_worse_is_a_failure():
    result = record_death_save(_Dice(9), dying())
    assert not result.success and result.combatant.death_saves.failures == 1


def test_a_natural_one_counts_twice():
    result = record_death_save(_Dice(1), dying())
    assert result.combatant.death_saves.failures == 2


def test_a_natural_twenty_puts_them_back_on_their_feet():
    """Not a success — a recovery, at 1 hit point. The rule most often played wrong."""
    result = record_death_save(_Dice(20), dying())
    assert result.revived and result.combatant.current_hp == 1
    assert not result.combatant.dying


def test_three_successes_stabilise():
    target = dying()
    for _ in range(DEATH_SAVES_NEEDED):
        target = record_death_save(_Dice(15), target).combatant
    assert Condition.STABLE in target.conditions and not target.dying


def test_three_failures_kill():
    target = dying()
    for _ in range(DEATH_SAVES_NEEDED):
        target = record_death_save(_Dice(4), target).combatant
    assert target.dead


def test_a_natural_one_from_two_failures_still_only_kills_once():
    target = record_death_save(_Dice(4), dying()).combatant
    target = record_death_save(_Dice(4), target).combatant
    result = record_death_save(_Dice(1), target)
    assert result.died and result.combatant.death_saves.failures == DEATH_SAVES_NEEDED


# --- initiative -------------------------------------------------------------


def test_initiative_is_highest_first():
    entries = roll_initiative(random.Random(3), [pc(), foe()])
    assert entries[0].total >= entries[1].total


def test_the_same_seed_gives_the_same_order():
    """A fight that cannot be replayed is not evidence of anything."""
    party = [pc(), foe(), foe("Bandit", initiative_modifier=1)]
    first = roll_initiative(random.Random(11), party)
    second = roll_initiative(random.Random(11), party)
    assert [e.combatant_id for e in first] == [e.combatant_id for e in second]
    assert [e.total for e in first] == [e.total for e in second]


def test_a_tie_falls_to_the_higher_dexterity():
    """5e hands ties to the DM, which is useless in an instrument."""
    quick = pc("Corin Vale", initiative_modifier=0, dexterity=4)
    slow = foe("Wolf", initiative_modifier=0, dexterity=1)
    entries = roll_initiative(_Dice(10, 10), [slow, quick])

    assert entries[0].combatant_id == quick.id
    assert entries[0].tiebreak == "" and entries[1].tiebreak == "dexterity"


def test_a_tie_on_dexterity_falls_to_the_party():
    ours = pc("Corin Vale", initiative_modifier=0, dexterity=2)
    theirs = foe("Wolf", initiative_modifier=0, dexterity=2)
    entries = roll_initiative(_Dice(10, 10), [theirs, ours])

    assert entries[0].combatant_id == ours.id
    assert entries[1].tiebreak == "side"


def test_a_tie_within_one_side_falls_to_the_name():
    first = foe("Bandit", initiative_modifier=0, dexterity=2)
    second = foe("Wolf", initiative_modifier=0, dexterity=2)
    entries = roll_initiative(_Dice(10, 10), [second, first])

    assert entries[0].combatant_id == first.id
    assert entries[1].tiebreak == "name"


# --- the encounter ----------------------------------------------------------


def encounter(*combatants, seed: int = 5) -> Encounter:
    return Encounter.start(random.Random(seed), list(combatants) or [pc(), foe()])


def test_an_encounter_opens_on_round_one():
    fight = encounter()
    assert fight.round == 1 and fight.turn_index == 0
    assert fight.active.id == fight.order[0]


def test_an_encounter_needs_somebody():
    with pytest.raises(CombatError):
        Encounter.start(random.Random(1), [])


def test_an_unknown_combatant_is_an_error():
    with pytest.raises(CombatError):
        encounter().get("nobody")


def test_the_turn_passes_down_the_order_and_rolls_into_the_next_round():
    fight = encounter()
    assert fight.advance().id == fight.order[1]
    assert fight.round == 1

    fight.advance()
    assert fight.round == 2 and fight.turn_index == 0


def test_a_downed_monster_is_skipped():
    fight = encounter(pc(), foe(), foe("Bandit"))
    fight.damage("bandit", 99)

    seen = [fight.advance().id for _ in range(3)]
    assert "bandit" not in seen


def test_a_dying_character_still_gets_their_turn():
    """That turn is where the death save happens. Skipping them would quietly take the
    clock out of the tensest part of the game."""
    fight = encounter(pc(), foe())
    fight.damage("corin", 12)

    seen = [fight.advance().id for _ in range(3)]
    assert "corin" in seen


def test_a_downed_combatant_gets_no_action_economy():
    fight = encounter(pc(), foe())
    fight.damage("corin", 12)
    while fight.active.id != "corin":
        fight.advance()
    assert fight.budget == TurnBudget(action=False, bonus_action=False, reaction=False, movement=0)


def test_each_turn_starts_with_a_fresh_budget():
    fight = encounter()
    fight.budget = fight.budget.spend_action().move(20)
    fight.advance()
    assert fight.budget.action and fight.budget.movement == 30


def test_the_fight_is_over_when_one_side_is_down():
    fight = encounter(pc(), foe())
    assert not fight.over

    fight.damage("wolf", 99)
    assert fight.over and fight.winner is Side.PARTY


def test_a_dying_character_does_not_count_as_standing():
    fight = encounter(pc(), foe())
    fight.damage("corin", 12)
    assert fight.over and fight.winner is Side.FOES


def test_healing_someone_back_up_reopens_the_fight():
    fight = encounter(pc(), foe())
    fight.damage("corin", 12)
    assert fight.over

    fight.heal("corin", 5)
    assert not fight.over and fight.winner is None


def test_a_death_save_through_the_encounter_updates_the_combatant():
    fight = encounter(pc(), foe())
    fight.damage("corin", 12)

    result = fight.death_save("corin", _Dice(15))
    assert result.success
    assert fight.get("corin").death_saves.successes == 1


def test_advancing_when_nobody_can_act_does_not_spin():
    fight = encounter(foe("Wolf"), foe("Bandit"))
    fight.damage("wolf", 99)
    fight.damage("bandit", 99)
    assert fight.advance() is not None


# --- the action economy -----------------------------------------------------


def test_spending_an_action_leaves_the_bonus_action():
    budget = TurnBudget().spend_action()
    assert not budget.action and budget.bonus_action


def test_movement_is_spent_down_and_clamped_at_zero():
    assert TurnBudget().move(10).movement == 20
    assert TurnBudget().move(999).movement == 0


def test_a_reaction_is_its_own_slot():
    budget = TurnBudget().spend_action().spend_bonus_action()
    assert budget.reaction


# --- immutability -----------------------------------------------------------


def test_damage_does_not_mutate_the_combatant_it_was_given():
    """A fight is a sequence of states, and holding two at once is what lets a caller
    show before-and-after without bookkeeping."""
    before = pc(hp=12)
    apply_damage(before, 5)
    assert before.current_hp == 12


def test_conditions_are_replaced_not_mutated():
    before = pc()
    after = before.with_conditions(add=(Condition.PRONE,))
    assert Condition.PRONE not in before.conditions
    assert Condition.PRONE in after.conditions


def test_being_dropped_on_your_own_turn_ends_it():
    """A reaction, a trap, ongoing damage. Handled at the one place state changes, so no
    caller can forget it."""
    fight = encounter(pc(), foe())
    while fight.active.id != "corin":
        fight.advance()
    assert fight.budget.action

    fight.damage("corin", 99)
    assert not fight.budget.action and fight.budget.movement == 0


# --- a whole fight ----------------------------------------------------------


def run_fight(seed: int) -> list[str]:
    """Play a fight to its end, deterministically, and return what happened.

    Both sides swing for a flat 4 rather than rolling attacks: the point is the state
    machine, and `resolve_attack` has its own tests. A round cap stops a bug turning a
    test run into a hang.
    """
    rng = random.Random(seed)
    fight = Encounter.start(
        rng, [pc("Corin Vale", hp=12), pc("Hammond", hp=14), foe("Wolf", hp=11), foe("Bandit", hp=9)]
    )
    transcript = [f"order: {[c.name for c in fight.in_order()]}"]

    while not fight.over and fight.round <= 20:
        actor = fight.active
        if actor.dying:
            result = fight.death_save(actor.id, rng)
            transcript.append(f"r{fight.round} {actor.name} death save {result.roll.natural}")
        elif actor.acts:
            target = next(
                (c for c in fight.combatants.values() if c.side is not actor.side and not c.down),
                None,
            )
            if target is not None:
                outcome = fight.damage(target.id, 4, "slashing")
                transcript.append(
                    f"r{fight.round} {actor.name} hits {target.name} "
                    f"-> {outcome.combatant.current_hp}hp"
                )
        fight.advance()

    transcript.append(f"winner: {fight.winner.value if fight.winner else 'none'}")
    return transcript


def test_a_whole_fight_replays_from_its_seed():
    """The property the whole module exists for: a logged fight can be re-run and be the
    same fight. Without it a combat log is a story, not evidence."""
    assert run_fight(42) == run_fight(42)


def test_different_seeds_are_different_fights():
    """Guards the test above from passing because nothing is random at all."""
    fights = {tuple(run_fight(seed)) for seed in range(8)}
    assert len(fights) > 1


def test_a_fight_ends():
    transcript = run_fight(42)
    assert transcript[-1] in ("winner: party", "winner: foes")
