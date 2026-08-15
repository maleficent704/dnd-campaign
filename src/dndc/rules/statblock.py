"""Turning stat blocks and sheets into combatants (P3.2).

`rules/combat.py` runs a fight over `Combatant`s. This is what builds them — from an SRD
monster, or from a player's `CharacterSheet`. Data in, data out; no repository, no disk,
no model, same as everything else in `rules/`.

Two places the SRD is prose rather than data, and both are handled the same way: **parse
what is certain, record what is not, and never split the difference.** That is the posture
the inventory parser was built on and the reason `[[CHECK]]` refuses to invent a DC — a
guess here does not cost a log line, it puts a wrong number in front of the players.

**Multiattack is a sentence.** "The elemental makes two slam attacks" resolves cleanly.
"The captain makes three melee attacks: two with its scimitar and one with its dagger. Or
the captain makes two ranged attacks with its daggers" does not, and pretending otherwise
would silently give a monster the wrong number of attacks. Of the 68 monsters in the
ingested set with a multiattack, the unambiguous forms resolve and the rest arrive
`resolved=False` carrying their text, for P3.4 to put in front of the table.

**Damage modifiers are sometimes qualified.** Four of them read like "bludgeoning,
piercing, and slashing from nonmagical weapons", and whether they apply depends on the
weapon swinging — which the engine cannot know from the stat block alone. Applying them
blindly would roughly double a monster's effective hit points against an ordinary party,
so they are kept in `qualified` and left unapplied until something knows enough to judge.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from dndc.rules.checks import ability_modifier
from dndc.rules.combat import Combatant, Condition, Side
from dndc.rules.dice import roll
from dndc.schema.sheet import Ability, CharacterSheet
from dndc.schema.srd import Monster, MonsterAction

#: `2d8`, `7d10` — a monster's hit dice, whose size also fixes the constitution bonus
#: (one per die). The SRD stores the dice without that bonus and the total with it.
_HIT_DICE = re.compile(r"^\s*(?P<count>\d+)d(?P<sides>\d+)\s*$")

#: "The elemental makes two slam attacks." The whole of the unambiguous form.
_SIMPLE_MULTIATTACK = re.compile(
    r"\bmakes\s+(?P<count>one|two|three|four|five|six)\s+(?P<what>[\w' -]+?)\s+attacks?\b",
    re.IGNORECASE,
)

#: "…: one with its beard and one with its glaive." The parts of a colon list.
_MULTIATTACK_PART = re.compile(
    r"\b(?P<count>one|two|three|four|five|six)\s+with\s+(?:its\s+|his\s+|her\s+|their\s+)?"
    r"(?P<what>[\w' -]+?)(?=\s*(?:,|\band\b|\.|$))",
    re.IGNORECASE,
)

#: A multiattack offering a choice, or hedged on a condition, is never resolved: the
#: engine would have to decide which branch the monster takes, and that is the GM's call.
_AMBIGUOUS = re.compile(r"\b(or|alternatively|instead|if it|if the)\b", re.IGNORECASE)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}

#: A damage-modifier string naming more than a bare type: "…from nonmagical weapons".
#: Whether it applies depends on the attack, which a stat block cannot say.
_QUALIFIED = re.compile(r"[,]|\bfrom\b|\bthat\b|\bnonmagical\b", re.IGNORECASE)

MULTIATTACK = "multiattack"


@dataclass(frozen=True)
class Attack:
    """One thing a combatant can do to another, ready for `resolve_attack`."""

    name: str
    attack_bonus: int
    damage_expression: str | None = None
    damage_type: str | None = None
    #: Save-based actions (a breath weapon) carry a DC instead of an attack bonus.
    save_ability: Ability | None = None
    save_dc: int | None = None
    description: str = ""

    @property
    def is_attack_roll(self) -> bool:
        return self.save_dc is None


@dataclass(frozen=True)
class Multiattack:
    """What a monster does when it acts, when the stat block says so in a sentence.

    `resolved` is the load-bearing field. False means the engine could not be sure, and
    the caller must not silently fall back to one attack — the text is here so it can be
    shown to whoever is running the fight.
    """

    raw: str
    #: How many attacks in total, when the sentence says. Zero when even that is unclear.
    count: int = 0
    #: (attack name, times) — only populated when every part resolved to a real action.
    parts: tuple[tuple[str, int], ...] = ()
    resolved: bool = False

    def render(self) -> str:
        if self.resolved:
            return ", ".join(f"{times}x {name}" for name, times in self.parts)
        return self.raw


@dataclass(frozen=True)
class StatBlock:
    """A monster made usable: a combatant template plus what it can do."""

    combatant: Combatant
    attacks: tuple[Attack, ...] = ()
    multiattack: Multiattack | None = None
    #: Damage modifiers the engine declined to apply, with the text that qualified them.
    qualified: tuple[str, ...] = ()

    def attack(self, name: str) -> Attack | None:
        wanted = name.strip().casefold()
        return next((a for a in self.attacks if a.name.casefold() == wanted), None)


# --- hit points -------------------------------------------------------------


def average_hit_points(monster: Monster) -> int:
    """What the stat block says. The default, because a table that wants the printed
    monster should get the printed monster."""
    return monster.hit_points


def rolled_hit_points(monster: Monster, rng: random.Random) -> int:
    """Roll the monster's hit dice, adding its constitution bonus once per die.

    The SRD stores the dice without the bonus (`2d8`) and the total with it (11 for a
    wolf), so the bonus has to be added back or every rolled monster comes out frail.
    Floored at 1: a creature that exists has at least one hit point.
    """
    match = _HIT_DICE.match(monster.hit_dice or "")
    if match is None:
        return average_hit_points(monster)
    count = int(match.group("count"))
    bonus = ability_modifier(monster.abilities.score(Ability.CON)) * count
    return max(1, roll(monster.hit_dice, rng).total + bonus)


# --- building combatants -----------------------------------------------------


def from_monster(
    monster: Monster,
    combatant_id: str | None = None,
    name: str | None = None,
    side: Side = Side.FOES,
    rng: random.Random | None = None,
) -> StatBlock:
    """A monster, ready to fight. Pass `rng` to roll hit points instead of taking the
    average — a table wanting variance opts into it, rather than getting it by default."""
    hit_points = rolled_hit_points(monster, rng) if rng is not None else average_hit_points(monster)
    resistances, qualified_resist = _damage_types(monster.damage_resistances)
    immunities, qualified_immune = _damage_types(monster.damage_immunities)
    vulnerabilities, qualified_vuln = _damage_types(monster.damage_vulnerabilities)

    combatant = Combatant(
        id=combatant_id or monster.index,
        name=name or monster.name,
        side=side,
        max_hp=hit_points,
        current_hp=hit_points,
        armor_class=monster.armor_class,
        initiative_modifier=ability_modifier(monster.abilities.score(Ability.DEX)),
        dexterity=monster.abilities.score(Ability.DEX),
        is_player=False,
        resistances=resistances,
        vulnerabilities=vulnerabilities,
        immunities=immunities,
        condition_immunities=_condition_immunities(monster),
    )
    attacks = tuple(
        built
        for action in monster.actions
        if not action.name.casefold().startswith(MULTIATTACK)
        for built in (_attack(action),)
        if built is not None
    )
    return StatBlock(
        combatant=combatant,
        attacks=attacks,
        multiattack=_multiattack(monster, attacks),
        qualified=tuple(qualified_resist + qualified_immune + qualified_vuln),
    )


def from_sheet(
    sheet: CharacterSheet, combatant_id: str | None = None, side: Side = Side.PARTY
) -> Combatant:
    """A player character, ready to fight. Their hit points are already on the sheet —
    combat reads them and P3.4 will write them back, which is the same
    engine-owns-the-numbers split every other part of this project runs on."""
    return Combatant(
        id=combatant_id or sheet.name.casefold().replace(" ", "-"),
        name=sheet.name,
        side=side,
        max_hp=sheet.hit_points.maximum,
        current_hp=sheet.hit_points.current,
        temporary_hp=sheet.hit_points.temporary,
        armor_class=sheet.armor_class,
        initiative_modifier=sheet.initiative_modifier,
        dexterity=sheet.abilities.score(Ability.DEX),
        is_player=True,
    )


# --- the prose bits ----------------------------------------------------------


def _attack(action: MonsterAction) -> Attack | None:
    """One action as something the engine can resolve, or None if it is narrative.

    An action with neither an attack bonus nor a save DC nor damage is a stat block
    describing behaviour rather than offering a mechanic; carrying it as an `Attack` would
    invite a caller to roll for it.
    """
    damage = action.damage[0] if action.damage else None
    if action.attack_bonus is None and action.dc_value is None and damage is None:
        return None
    return Attack(
        name=action.name,
        attack_bonus=action.attack_bonus or 0,
        damage_expression=damage.damage_dice if damage and damage.damage_dice else None,
        damage_type=damage.damage_type if damage else None,
        save_ability=action.dc_ability,
        save_dc=action.dc_value,
        description=action.description,
    )


def _multiattack(monster: Monster, attacks: tuple[Attack, ...]) -> Multiattack | None:
    action = next(
        (a for a in monster.actions if a.name.casefold().startswith(MULTIATTACK)), None
    )
    if action is None:
        return None

    text = " ".join((action.description or "").split())
    if not text:
        return Multiattack(raw=action.name)
    if _AMBIGUOUS.search(text):
        # A choice or a condition. Which branch the monster takes is the GM's call, and
        # picking one here would be the engine deciding tactics.
        return Multiattack(raw=text, count=_stated_count(text))

    parts = _named_parts(text, attacks)
    if parts:
        return Multiattack(
            raw=text, count=sum(times for _, times in parts), parts=parts, resolved=True
        )

    simple = _SIMPLE_MULTIATTACK.search(text)
    if simple is not None:
        count = _NUMBER_WORDS[simple.group("count").lower()]
        matched = _match_attack(simple.group("what"), attacks)
        if matched is not None:
            return Multiattack(
                raw=text, count=count, parts=((matched.name, count),), resolved=True
            )
        return Multiattack(raw=text, count=count)

    return Multiattack(raw=text, count=_stated_count(text))


def _named_parts(text: str, attacks: tuple[Attack, ...]) -> tuple[tuple[str, int], ...]:
    """"…: one with its beard and one with its glaive" — but only if every part lands.

    All-or-nothing on purpose. A partly-resolved multiattack is a monster with the wrong
    number of attacks, which is worse than one the caller knows it has to ask about.
    """
    if ":" not in text:
        return ()
    found = list(_MULTIATTACK_PART.finditer(text.split(":", 1)[1]))
    if not found:
        return ()

    parts = []
    for match in found:
        attack = _match_attack(match.group("what"), attacks)
        if attack is None:
            return ()
        parts.append((attack.name, _NUMBER_WORDS[match.group("count").lower()]))
    return tuple(parts)


def _match_attack(phrase: str, attacks: tuple[Attack, ...]) -> Attack | None:
    """Find the action a multiattack sentence is pointing at.

    Matched on whole words rather than substrings: "claw" must not select "Claws of the
    Deep" merely for sharing letters, and a stat block naming an attack the block does not
    have is exactly the case that has to fail rather than approximate.
    """
    wanted = {word for word in re.findall(r"[a-z]+", phrase.casefold()) if len(word) > 2}
    if not wanted:
        return None
    for attack in attacks:
        words = {word for word in re.findall(r"[a-z]+", attack.name.casefold())}
        if wanted & words:
            return attack
    return None


def _stated_count(text: str) -> int:
    match = _SIMPLE_MULTIATTACK.search(text)
    return _NUMBER_WORDS[match.group("count").lower()] if match else 0


def _damage_types(values: tuple[str, ...]) -> tuple[frozenset[str], list[str]]:
    """Split bare damage types from qualified ones.

    "fire" is a rule the engine can apply. "bludgeoning, piercing, and slashing from
    nonmagical weapons" depends on the weapon swinging, and granting it unconditionally
    would roughly double a monster's effective hit points against an ordinary party — a
    silent, large, and entirely wrong buff.
    """
    plain: set[str] = set()
    qualified: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            continue
        if _QUALIFIED.search(text):
            qualified.append(text)
        else:
            plain.add(text.casefold())
    return frozenset(plain), qualified


def _condition_immunities(monster: Monster) -> frozenset[Condition]:
    """Condition immunities the combat core knows about. The rest stay narrative.

    Note the field this lands in: `condition_immunities`, not `conditions`. Writing it to
    the latter — which an earlier draft of this function did — marks a monster immune to
    being knocked prone as lying on the floor.
    """
    known = {condition.value: condition for condition in Condition}
    return frozenset(
        known[name.strip().casefold()]
        for name in monster.condition_immunities
        if name.strip().casefold() in known
    )


__all__ = [
    "Attack",
    "Multiattack",
    "StatBlock",
    "average_hit_points",
    "from_monster",
    "from_sheet",
    "rolled_hit_points",
]
