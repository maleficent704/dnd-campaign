"""P3.6 — the combat view, and a player who chooses their own action.

Two things close Phase 3 here.

**The view is the authoritative numeric display (OD-11).** The GM narrates qualitatively
and never states a value; this is where the values live, rendered from state rather than
from anything a model said. That division only works if the display is actually right, so
the bar gets its own tests.

**Weapons come off the sheet.** Every number in an attack is derived — the ability from
the weapon's own properties, proficiency from what the character is trained in, damage
from the SRD entry — which is the reason inventory is state (P2.4) rather than flavour.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from dndc.game.cli import choose, hp_bar, player_turn, render_encounter
from dndc.game.combatturn import AttackPlan
from dndc.rules.combat import Combatant, Condition, Encounter, Side
from dndc.rules.statblock import Attack, unarmed_for, weapons_for
from dndc.schema.sheet import AbilityScores, CharacterSheet, HitPoints, InventoryItem
from dndc.srd.repository import SRDRepository

import random


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


def sheet(**overrides) -> CharacterSheet:
    data = dict(
        name="Corin Vale", player="Kelly", species="Human", character_class="Rogue",
        level=1,
        abilities=AbilityScores(str=8, dex=16, con=12, int=12, wis=11, cha=14),
        hit_points=HitPoints(maximum=9, current=9),
        armor_class=14,
        proficiencies={"weapons": ["Simple Weapons", "Rapiers"]},
    )
    data.update(overrides)
    return CharacterSheet(**data)


def combatant(name="Corin Vale", hp=20, current=None, **overrides) -> Combatant:
    data = dict(
        id=name.split()[0].lower(), name=name, side=Side.PARTY, max_hp=hp,
        current_hp=hp if current is None else current, armor_class=14, is_player=True,
    )
    data.update(overrides)
    return Combatant(**data)


def recorder() -> Console:
    return Console(force_terminal=False, no_color=True, record=True, width=100)


# --- the hit-point bar --------------------------------------------------------


def test_a_full_bar_is_full():
    assert hp_bar(20, 20, width=8) == "########"


def test_an_empty_bar_is_empty():
    assert hp_bar(0, 20, width=8) == "--------"


def test_a_living_combatant_never_shows_an_empty_bar():
    """1 of 40 rounds to zero eighths, and an empty bar beside a living character is the
    display contradicting the number next to it."""
    assert hp_bar(1, 40, width=8).startswith("#")


def test_the_bar_tracks_the_fraction():
    assert hp_bar(10, 20, width=8) == "####----"


def test_a_maximum_of_zero_does_not_divide_by_zero():
    assert hp_bar(0, 0, width=6) == "      "


# --- the initiative view ------------------------------------------------------


def test_the_view_shows_hit_points_from_state():
    """The one place a total is allowed to appear (OD-11), and it comes from the
    encounter rather than from anything a model said."""
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)])
    encounter.damage("wolf", 4)

    render_encounter(console, encounter)
    output = console.export_text()

    assert "7/11" in output and "20/20" in output


def test_the_active_combatant_is_marked():
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)])

    render_encounter(console, encounter)
    marked = [line for line in console.export_text().splitlines() if line.strip().startswith(">")]

    assert len(marked) == 1 and encounter.active.name in marked[0]


def test_a_dying_character_shows_their_death_save_tally():
    """The tally is state the players need and the GM must not narrate."""
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(hp=10), combatant("Wolf", 11, side=Side.FOES, is_player=False)])
    encounter.damage("corin", 10)
    encounter.death_save("corin", random.Random(3))

    render_encounter(console, encounter)
    assert "down" in console.export_text()


def test_a_dead_combatant_reads_as_dead_not_as_down():
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)])
    encounter.damage("wolf", 99)

    render_encounter(console, encounter)
    assert "dead" in console.export_text()


def test_conditions_worth_seeing_are_shown():
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)])
    encounter.replace_combatant(
        encounter.get("corin").with_conditions(add=(Condition.PRONE,))
    )

    render_encounter(console, encounter)
    # Parentheses rather than brackets: rich reads `[prone]` as a style tag and eats it.
    assert "(prone)" in console.export_text()


def test_unconscious_is_not_repeated_beside_the_hit_points():
    """The hit-point column already says it; saying it twice is noise."""
    console = recorder()
    encounter = Encounter.start(random.Random(1), [combatant(hp=10), combatant("Wolf", 11, side=Side.FOES, is_player=False)])
    encounter.damage("corin", 10)

    render_encounter(console, encounter)
    assert "unconscious" not in console.export_text()


# --- choosing -----------------------------------------------------------------


def test_a_number_picks_that_option(monkeypatch):
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "2")
    assert choose(recorder(), "pick", ["a", "b", "c"]) == 1


def test_an_out_of_range_answer_is_asked_again(monkeypatch):
    answers = iter(["9", "1"])
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: next(answers))
    assert choose(recorder(), "pick", ["a", "b"]) == 0


def test_nobody_at_the_keyboard_chooses_nothing(monkeypatch):
    def _eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("dndc.game.cli.Prompt.ask", _eof)
    assert choose(recorder(), "pick", ["a"]) is None


def test_an_unreadable_answer_runs_out_rather_than_guessing(monkeypatch):
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: "wat")
    assert choose(recorder(), "pick", ["a", "b"], attempts=2) is None


# --- a player's turn ----------------------------------------------------------


def rapier() -> Attack:
    return Attack(name="Rapier", attack_bonus=5, damage_expression="1d8+3", damage_type="piercing")


def test_a_player_picks_a_weapon_and_a_target(monkeypatch):
    answers = iter(["1", "2"])
    monkeypatch.setattr("dndc.game.cli.Prompt.ask", lambda *a, **k: next(answers))
    encounter = Encounter.start(
        random.Random(1),
        [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False),
         combatant("Bandit", 11, side=Side.FOES, is_player=False)],
    )

    plan = player_turn(recorder(), encounter, encounter.get("corin"), [rapier()])

    assert isinstance(plan, AttackPlan) and len(plan.attacks) == 1
    assert plan.attacks[0].attack.name == "Rapier"


def test_a_single_enemy_is_not_a_question(monkeypatch):
    """Asking "at whom?" when there is one of them is the interface wasting a keystroke."""
    asked = []

    def _ask(prompt, **kwargs):
        asked.append(prompt)
        return "1"

    monkeypatch.setattr("dndc.game.cli.Prompt.ask", _ask)
    encounter = Encounter.start(
        random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)]
    )
    player_turn(recorder(), encounter, encounter.get("corin"), [rapier()])

    assert len(asked) == 1


def test_a_player_with_nothing_to_hit_takes_no_turn():
    encounter = Encounter.start(
        random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)]
    )
    encounter.damage("wolf", 99)
    assert player_turn(recorder(), encounter, encounter.get("corin"), [rapier()]) is None


def test_a_player_with_no_weapons_takes_no_turn():
    encounter = Encounter.start(
        random.Random(1), [combatant(), combatant("Wolf", 11, side=Side.FOES, is_player=False)]
    )
    assert player_turn(recorder(), encounter, encounter.get("corin"), []) is None


# --- weapons off the sheet ----------------------------------------------------


def test_a_finesse_weapon_uses_the_better_ability(repo):
    """Read off the weapon's own properties rather than guessed from its name."""
    carried = sheet(inventory=[InventoryItem(name="rapier")])
    (attack,) = weapons_for(carried, repo)

    # dex 16 (+3) beats str 8 (-1), plus proficiency 2.
    assert attack.attack_bonus == 5 and attack.damage_expression == "1d8+3"
    assert attack.damage_type == "piercing"


def test_a_ranged_weapon_uses_dexterity(repo):
    carried = sheet(inventory=[InventoryItem(name="shortbow")])
    (attack,) = weapons_for(carried, repo)
    assert attack.attack_bonus == 5


def test_a_heavy_weapon_uses_strength(repo):
    strong = sheet(
        abilities=AbilityScores(str=16, dex=10, con=12, int=10, wis=10, cha=10),
        proficiencies={"weapons": ["Martial Weapons"]},
        inventory=[InventoryItem(name="greataxe")],
    )
    (attack,) = weapons_for(strong, repo)
    assert attack.attack_bonus == 5 and attack.damage_expression.endswith("+3")


def test_a_weapon_you_are_not_trained_in_still_swings(repo):
    """Not proficient is a penalty, not an error — you just do not add the bonus."""
    untrained = sheet(
        proficiencies={"weapons": []}, inventory=[InventoryItem(name="rapier")]
    )
    (attack,) = weapons_for(untrained, repo)
    assert attack.attack_bonus == 3  # dex only


def test_proficiency_matches_a_category_or_a_specific_weapon(repo):
    by_category = sheet(
        proficiencies={"weapons": ["Simple Weapons"]},
        inventory=[InventoryItem(name="dagger")],
    )
    by_name = sheet(
        proficiencies={"weapons": ["Rapiers"]},
        inventory=[InventoryItem(name="rapier")],
    )
    assert weapons_for(by_category, repo)[0].attack_bonus == 5
    assert weapons_for(by_name, repo)[0].attack_bonus == 5


def test_things_that_are_not_weapons_are_skipped(repo):
    carried = sheet(inventory=[InventoryItem(name="bedroll"), InventoryItem(name="rapier")])
    assert [a.name for a in weapons_for(carried, repo)] == ["Rapier"]


def test_a_character_carrying_nothing_still_has_their_hands(repo):
    empty = sheet()
    assert weapons_for(empty, repo) == ()
    assert unarmed_for(empty).name == "unarmed strike"


def test_the_real_party_gets_the_weapons_on_their_sheets(repo):
    """Against the campaign's actual characters, because a derivation that only works on
    fixtures is not a derivation."""
    corin = CharacterSheet.load("campaigns/the-salt-road/characters/corin-vale.yaml")
    names = {a.name for a in weapons_for(corin, repo)}
    assert "Rapier" in names and "Shortbow" in names
