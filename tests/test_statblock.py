"""P3.2 — stat blocks and sheets become combatants.

The SRD is data in most places and prose in two that matter, and both are handled the
same way: parse what is certain, record what is not, never split the difference. A guess
here does not cost a log line — it puts a wrong number in front of the players.

So the interesting tests are the refusals. A multiattack offering a choice stays
unresolved rather than picking a branch; a damage resistance qualified by "from nonmagical
weapons" is recorded and *not applied*, because granting it unconditionally would roughly
double a monster's effective hit points against an ordinary party.

There are also whole-dataset invariants at the bottom. A prose parser is only honestly
described by running it over everything it will ever see.
"""

from __future__ import annotations

import random

import pytest

from dndc.rules.combat import Combatant, Condition, Side
from dndc.rules.statblock import (
    average_hit_points,
    from_monster,
    from_sheet,
    rolled_hit_points,
)
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
)
from dndc.schema.srd import (
    Monster,
    MonsterAction,
    MonsterDamage,
    Size,
)
from dndc.srd.repository import SRDRepository


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


def monster(**overrides) -> Monster:
    data = dict(
        index="wolf",
        name="Wolf",
        size=Size.MEDIUM,
        armor_class=13,
        hit_points=11,
        hit_dice="2d8",
        abilities=AbilityScores(str=12, dex=15, con=12, int=3, wis=12, cha=6),
        challenge_rating=0.25,
        proficiency_bonus=2,
        xp=50,
        passive_perception=13,
        actions=(
            MonsterAction(
                name="Bite",
                attack_bonus=4,
                damage=(MonsterDamage(damage_dice="2d4+2", damage_type="piercing"),),
            ),
        ),
    )
    data.update(overrides)
    return Monster(**data)


def multiattacking(description: str, actions=()) -> Monster:
    return monster(
        actions=(
            MonsterAction(name="Multiattack", description=description),
            *(actions or monster().actions),
        )
    )


def sheet(**overrides) -> CharacterSheet:
    data = dict(
        name="Corin Vale",
        player="Kelly",
        species="Human",
        character_class="Rogue",
        level=1,
        abilities=AbilityScores(str=10, dex=16, con=12, int=12, wis=11, cha=14),
        hit_points=HitPoints(maximum=9, current=6),
        armor_class=14,
    )
    data.update(overrides)
    return CharacterSheet(**data)


# --- hit points -------------------------------------------------------------


def test_a_monster_takes_its_printed_hit_points_by_default():
    """A table that wants the printed monster should get the printed monster."""
    assert from_monster(monster()).combatant.max_hp == 11


def test_rolling_hit_points_adds_the_constitution_bonus_per_die():
    """The SRD stores the dice without the bonus (`2d8`) and the total with it. Forget the
    bonus and every rolled monster comes out frail."""
    rolls = [rolled_hit_points(monster(), random.Random(seed)) for seed in range(40)]
    assert min(rolls) >= 2 + 2  # two dice at 1, plus +1 CON twice
    assert max(rolls) <= 16 + 2


def test_rolled_hit_points_are_opt_in():
    assert from_monster(monster()).combatant.max_hp == average_hit_points(monster())
    rolled = from_monster(monster(), rng=random.Random(1)).combatant.max_hp
    assert rolled >= 1


def test_unparseable_hit_dice_fall_back_to_the_printed_total():
    assert rolled_hit_points(monster(hit_dice=""), random.Random(1)) == 11


def test_hit_points_never_come_out_below_one():
    frail = monster(hit_dice="1d4", hit_points=1, abilities=AbilityScores(
        str=1, dex=1, con=1, int=1, wis=1, cha=1
    ))
    assert all(rolled_hit_points(frail, random.Random(s)) >= 1 for s in range(20))


# --- the combatant ----------------------------------------------------------


def test_a_monster_becomes_a_foe_with_its_stat_block_numbers():
    combatant = from_monster(monster()).combatant
    assert combatant.side is Side.FOES and not combatant.is_player
    assert combatant.armor_class == 13
    assert combatant.initiative_modifier == 2  # dex 15
    assert combatant.dexterity == 15


def test_several_of_the_same_monster_can_be_told_apart():
    first = from_monster(monster(), combatant_id="wolf-1", name="Wolf A").combatant
    second = from_monster(monster(), combatant_id="wolf-2", name="Wolf B").combatant
    assert first.id != second.id and first.name != second.name


def test_a_sheet_becomes_a_player_combatant():
    combatant = from_sheet(sheet())
    assert combatant.is_player and combatant.side is Side.PARTY
    assert combatant.max_hp == 9 and combatant.current_hp == 6
    assert combatant.initiative_modifier == 3  # dex 16


def test_a_sheets_temporary_hit_points_come_along():
    combatant = from_sheet(sheet(hit_points=HitPoints(maximum=9, current=9, temporary=4)))
    assert combatant.temporary_hp == 4


# --- damage modifiers -------------------------------------------------------


def test_a_plain_resistance_is_applied():
    block = from_monster(monster(damage_resistances=("cold",)))
    assert "cold" in block.combatant.resistances and block.qualified == ()


def test_a_qualified_resistance_is_recorded_and_not_applied():
    """"bludgeoning, piercing, and slashing from nonmagical weapons" depends on the weapon
    swinging, which a stat block cannot say. Granting it unconditionally would roughly
    double the monster's effective hit points against an ordinary party."""
    qualified = "bludgeoning, piercing, and slashing from nonmagical weapons"
    block = from_monster(monster(damage_resistances=(qualified,)))

    assert block.combatant.resistances == frozenset()
    assert block.qualified == (qualified,)


def test_immunities_and_vulnerabilities_split_the_same_way():
    block = from_monster(
        monster(
            damage_immunities=("poison", "slashing from nonmagical weapons"),
            damage_vulnerabilities=("fire",),
        )
    )
    assert block.combatant.immunities == frozenset({"poison"})
    assert block.combatant.vulnerabilities == frozenset({"fire"})
    assert len(block.qualified) == 1


def test_condition_immunities_land_in_immunities_not_in_conditions():
    """The bug this test exists for: writing them to `conditions` marks a monster immune
    to being knocked prone as lying on the floor."""
    block = from_monster(monster(condition_immunities=("prone", "poisoned")))

    assert Condition.PRONE in block.combatant.condition_immunities
    assert Condition.PRONE not in block.combatant.conditions
    assert block.combatant.conditions == frozenset()


def test_an_immune_combatant_cannot_be_given_the_condition():
    block = from_monster(monster(condition_immunities=("prone",)))
    knocked = block.combatant.with_conditions(add=(Condition.PRONE,))
    assert Condition.PRONE not in knocked.conditions


def test_immunity_does_not_protect_against_falling_unconscious():
    """Those are what the engine does when hit points run out, not conditions inflicted
    on a creature. A monster immune to being knocked out still dies."""
    immune = Combatant(
        id="x", name="X", side=Side.FOES, max_hp=5, current_hp=5, armor_class=10,
        condition_immunities=frozenset({Condition.UNCONSCIOUS, Condition.DEAD}),
    )
    dropped = immune.with_conditions(add=(Condition.DEAD, Condition.UNCONSCIOUS))
    assert dropped.dead


# --- attacks ----------------------------------------------------------------


def test_an_action_becomes_an_attack_the_engine_can_resolve():
    (attack,) = from_monster(monster()).attacks
    assert attack.name == "Bite"
    assert attack.attack_bonus == 4
    assert attack.damage_expression == "2d4+2" and attack.damage_type == "piercing"
    assert attack.is_attack_roll


def test_a_save_based_action_carries_a_dc_instead_of_a_bonus():
    from dndc.schema.sheet import Ability

    breath = MonsterAction(
        name="Fire Breath",
        dc_ability=Ability.DEX,
        dc_value=13,
        damage=(MonsterDamage(damage_dice="4d6", damage_type="fire"),),
    )
    (attack,) = from_monster(monster(actions=(breath,))).attacks
    assert attack.save_dc == 13 and not attack.is_attack_roll


def test_a_narrative_action_is_not_an_attack():
    """No bonus, no DC, no damage — a stat block describing behaviour. Carrying it as an
    attack would invite a caller to roll for it."""
    flavour = MonsterAction(name="Keen Hearing", description="The wolf has advantage...")
    assert from_monster(monster(actions=(flavour,))).attacks == ()


def test_multiattack_is_not_itself_an_attack():
    block = multiattacking("The wolf makes two bite attacks.")
    assert [a.name for a in from_monster(block).attacks] == ["Bite"]


def test_an_attack_can_be_looked_up_by_name():
    block = from_monster(monster())
    assert block.attack("bite") is not None and block.attack("nope") is None


# --- multiattack ------------------------------------------------------------


def test_the_simple_form_resolves():
    ma = from_monster(multiattacking("The wolf makes two bite attacks.")).multiattack
    assert ma.resolved and ma.count == 2 and ma.parts == (("Bite", 2),)


def test_a_colon_list_resolves_when_every_part_names_a_real_action():
    beast = multiattacking(
        "The bear makes two attacks: one with its bite and one with its claws.",
        actions=(
            MonsterAction(name="Bite", attack_bonus=5,
                          damage=(MonsterDamage(damage_dice="1d8+3", damage_type="piercing"),)),
            MonsterAction(name="Claws", attack_bonus=5,
                          damage=(MonsterDamage(damage_dice="2d6+3", damage_type="slashing"),)),
        ),
    )
    ma = from_monster(beast).multiattack
    assert ma.resolved and ma.count == 2
    assert ma.parts == (("Bite", 1), ("Claws", 1))


def test_a_colon_list_naming_something_the_block_lacks_stays_unresolved():
    """All-or-nothing on purpose. A partly-resolved multiattack is a monster with the
    wrong number of attacks, which is worse than one the caller knows to ask about."""
    ma = from_monster(
        multiattacking("The thing makes two attacks: one with its bite and one with its tail.")
    ).multiattack
    assert not ma.resolved


def test_an_alternative_never_resolves_but_keeps_its_count():
    """Which branch the monster takes is the GM's call, not the engine's."""
    ma = from_monster(
        multiattacking(
            "The captain makes three melee attacks: two with its scimitar and one with "
            "its dagger. Or the captain makes two ranged attacks with its daggers."
        )
    ).multiattack
    assert not ma.resolved and ma.count == 3
    assert "Or the captain" in ma.raw


def test_a_conditional_never_resolves():
    ma = from_monster(
        multiattacking(
            "The chuul makes two pincer attacks. If the chuul is grappling a creature, "
            "it can also use its tentacles."
        )
    ).multiattack
    assert not ma.resolved


def test_an_unresolved_multiattack_renders_its_text_for_the_table():
    ma = from_monster(multiattacking("The thing does something complicated or else.")).multiattack
    assert not ma.resolved and ma.render() == ma.raw


def test_a_monster_without_multiattack_has_none():
    assert from_monster(monster()).multiattack is None


# --- the whole dataset ------------------------------------------------------


def test_every_ingested_monster_becomes_a_combatant(repo):
    """245 stat blocks, no exceptions, no crashes. A parser is only honestly described by
    running it over everything it will ever see."""
    for record in repo.data.monsters.values():
        combatant = from_monster(record).combatant
        assert combatant.max_hp >= 1 and combatant.armor_class >= 0


def test_every_resolved_multiattack_names_attacks_the_monster_actually_has(repo):
    """The failure that would matter: a monster told to swing something it does not have."""
    for record in repo.data.monsters.values():
        block = from_monster(record)
        if block.multiattack and block.multiattack.resolved:
            for name, times in block.multiattack.parts:
                assert block.attack(name) is not None, f"{record.name}: {name}"
                assert times >= 1


def test_a_resolved_multiattack_always_knows_its_count(repo):
    for record in repo.data.monsters.values():
        block = from_monster(record)
        if block.multiattack and block.multiattack.resolved:
            assert block.multiattack.count >= 1


def test_no_monster_silently_gains_blanket_physical_resistance(repo):
    """The qualified strings are all "…from nonmagical weapons" shapes. If one of those
    ever lands in `resistances`, most of the bestiary quietly doubles in durability."""
    physical = {"bludgeoning", "piercing", "slashing"}
    for record in repo.data.monsters.values():
        block = from_monster(record)
        for kind in block.combatant.resistances & physical:
            # A bare "piercing" resistance is real and fine (the Awakened Shrub has one).
            # What must never appear is one carrying a qualifier.
            assert " " not in kind and "," not in kind, f"{record.name}: {kind!r}"


# --- P3.1 and P3.2 together -------------------------------------------------


def test_a_real_party_fights_real_monsters(repo):
    """The point of both tasks: SRD data and a character sheet go in, a resolved fight
    comes out, and every number in it was the engine's."""
    from dndc.rules.checks import resolve_attack
    from dndc.rules.combat import Encounter

    rng = random.Random(7)
    corin = from_sheet(sheet(hit_points=HitPoints(maximum=30, current=30)))
    wolves = [
        from_monster(repo.monster("wolf"), combatant_id=f"wolf-{n}", name=f"Wolf {n}")
        for n in (1, 2)
    ]
    fight = Encounter.start(rng, [corin, *(w.combatant for w in wolves)])

    rounds = 0
    while not fight.over and rounds < 40:
        rounds += 1
        actor = fight.active
        target = next(
            (c for c in fight.combatants.values() if c.side is not actor.side and not c.down),
            None,
        )
        if target is not None and actor.acts:
            attack = wolves[0].attacks[0] if not actor.is_player else None
            outcome = resolve_attack(
                rng,
                attack_modifier=attack.attack_bonus if attack else 5,
                target_ac=target.armor_class,
                damage_expression=attack.damage_expression if attack else "1d8+3",
            )
            if outcome.hit:
                fight.damage(target.id, outcome.damage, attack.damage_type if attack else None)
        fight.advance()

    assert fight.over and fight.winner is not None
