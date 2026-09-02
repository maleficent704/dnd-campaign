"""Turning a co-creation concept into a validated character (P1.4).

D-005 puts the GM in charge of allocation mechanics "for" the player. D-001 puts the
engine in charge of whether the result is legal. This module is where those meet: the
GM's proposal comes in as a `Concept`, and a validated `CharacterSheet` comes out or
nothing does.

**The GM proposes an ordering, not numbers.** It says "dexterity matters most for this
concept, then constitution", and the engine maps the standard array onto that ranking.
This is OD-12's governing principle applied to allocation: the judgment genuinely being
made is ordinal ("what does this character care about"), the integers are arithmetic, and
arithmetic is the engine's job. It also makes an illegal spread *unrepresentable* rather
than merely rejected — a permutation of six abilities can only ever produce a legal
standard array, so there is no retry loop and no way for the model's point-buy arithmetic
to be wrong. Point buy works the same way: the GM picks a named shape, all of which cost
exactly the budget.

Everything here is a pure function over SRD data. No model calls, no RNG — the same
concept always builds the same sheet, which is what lets a co-creation transcript be
replayed in Phase 7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from dndc.rules.allocate import (
    STANDARD_ARRAY,
    AllocationError,
    apply_bonuses,
    assign_point_buy,
    assign_standard_array,
)
from dndc.rules.checks import Proficiency, ability_modifier
from dndc.schema.sheet import (
    AbilityScores,
    Ability,
    CharacterSheet,
    HitPoints,
    InventoryItem,
    Proficiencies,
    Skill,
    SpellSlotLevel,
)
from dndc.srd.repository import SRDRepository

#: Resolves a campaign-written background by name. `BackgroundBook.get` is the one the
#: game layer passes; the annotation is structural so this module imports no campaign code.
BackgroundLookup = Callable[[str], object | None]

#: Allocation methods the GM may name.
STANDARD_ARRAY_METHOD = "standard_array"
POINT_BUY_METHOD = "point_buy"

#: Point-buy spreads, highest first. Each costs exactly the 27-point budget — which
#: `assign_point_buy` re-checks anyway, because a table nobody validates is a table that
#: eventually drifts.
POINT_BUY_SHAPES: dict[str, tuple[int, ...]] = {
    #: Three specialists and three dump stats. 9+9+9 = 27.
    "focused": (15, 15, 15, 8, 8, 8),
    #: The standard array's shape, bought. 9+7+5+4+2+0 = 27.
    "balanced": (15, 14, 13, 12, 10, 8),
    #: No weaknesses, no peaks. 5+5+5+4+4+4 = 27.
    "even": (13, 13, 13, 12, 12, 12),
}
DEFAULT_SHAPE = "balanced"

#: SRD proficiency indexes are prefixed by kind: `skill-stealth`, `saving-throw-dex`.
_SKILL_PREFIX = "skill-"

#: SRD proficiency categories, grouped onto the sheet's fields. "Other" carries
#: thieves' tools, which is why it belongs with the tools rather than being dropped.
_ARMOR = frozenset({"Armor"})
_WEAPONS = frozenset({"Weapons"})
_TOOLS = frozenset({"Artisan's Tools", "Musical Instruments", "Gaming Sets", "Vehicles",
                    "Other"})

#: Every 5e character starts with at least 1 HP however punishing their constitution.
MIN_HIT_POINTS = 1

_UNARMORED_BASE_AC = 10
_SHIELD_AC = 2


class BuildError(ValueError):
    """The concept cannot become a legal character."""


@dataclass(frozen=True)
class Concept:
    """What the GM proposes at the end of the interview.

    Deliberately not a sheet: no scores, no HP, no AC, no modifiers. Those are all
    derived, and deriving them is the engine's half of D-005.
    """

    name: str
    player: str
    species: str
    character_class: str
    #: All six abilities, most important first. The engine turns this into scores.
    priority: tuple[Ability, ...]
    skills: tuple[Skill, ...] = ()
    background: str | None = None
    method: str = STANDARD_ARRAY_METHOD
    shape: str = DEFAULT_SHAPE
    #: Abilities taking a species' floating +1s (Half-Elf picks two).
    ability_bonus_picks: tuple[Ability, ...] = ()
    #: Skills (or "thieves' tools") upgraded to expertise by a class feature.
    expertise: tuple[str, ...] = ()
    #: Extra languages chosen from the species' options.
    languages: tuple[str, ...] = ()
    #: SRD equipment names. Armor and shield feed AC; the rest is carried kit.
    armor: str | None = None
    shield: bool = False
    equipment: tuple[str, ...] = ()
    spells: tuple[str, ...] = ()
    backstory: str = ""
    #: Free-text facts about the character, destined for the canon ledger (D-002).
    facts: tuple[str, ...] = field(default_factory=tuple)


def allocate_by_priority(
    priority: tuple[Ability, ...],
    method: str = STANDARD_ARRAY_METHOD,
    shape: str = DEFAULT_SHAPE,
) -> AbilityScores:
    """Map an ability ranking onto a legal spread, highest value to highest priority."""
    if len(set(priority)) != len(Ability) or len(priority) != len(Ability):
        listed = ", ".join(a.value for a in priority) or "(nothing)"
        raise BuildError(
            f"ability priority must list all six abilities exactly once, got: {listed}"
        )

    if method == STANDARD_ARRAY_METHOD:
        values = STANDARD_ARRAY
        assign = assign_standard_array
    elif method == POINT_BUY_METHOD:
        if shape not in POINT_BUY_SHAPES:
            raise BuildError(
                f"unknown point-buy shape {shape!r} "
                f"(expected one of: {', '.join(sorted(POINT_BUY_SHAPES))})"
            )
        values = POINT_BUY_SHAPES[shape]
        assign = assign_point_buy
    else:
        raise BuildError(
            f"unknown allocation method {method!r} "
            f"(expected {STANDARD_ARRAY_METHOD} or {POINT_BUY_METHOD})"
        )

    assignment = dict(zip(priority, values, strict=True))
    try:
        return assign(assignment)
    except AllocationError as exc:  # a shape table that stopped being legal
        raise BuildError(str(exc)) from exc


def class_skill_options(character_class) -> tuple[set[Skill], int]:
    """The skills a class may choose from, and how many it chooses.

    Read off the SRD's own `proficiency_choices` rather than a hand-kept table, so the
    answer to "can a fighter take arcana" comes from the ruleset.
    """
    allowed: set[Skill] = set()
    choose = 0
    for choice in character_class.proficiency_choices:
        skills = {
            skill
            for option in choice.options
            if (skill := _skill_from_index(option)) is not None
        }
        if skills:
            allowed |= skills
            choose += choice.choose
    return allowed, choose


def _skill_from_index(index: str) -> Skill | None:
    if not index.startswith(_SKILL_PREFIX):
        return None
    try:
        return Skill(index[len(_SKILL_PREFIX):].replace("-", "_"))
    except ValueError:
        return None


def build_character(
    concept: Concept,
    repo: SRDRepository,
    backgrounds: BackgroundLookup | None = None,
) -> CharacterSheet:
    """Build a validated level-1 sheet, or raise `BuildError` explaining why not.

    `backgrounds` resolves a background the *campaign* wrote (the 2026-08-15 (c) ruling),
    consulted after the SRD's own. Passed in rather than imported, the way `apply_gain`
    takes its catalogue: this module stays a pure function over the ruleset, and campaign
    content reaches it as an argument.
    """
    species = repo.species(concept.species)
    if species is None:
        raise BuildError(f"no SRD species called {concept.species!r}")
    character_class = repo.character_class(concept.character_class)
    if character_class is None:
        raise BuildError(f"no SRD class called {concept.character_class!r}")

    base = allocate_by_priority(concept.priority, concept.method, concept.shape)
    try:
        scores = apply_bonuses(base, _all_bonuses(concept, species))
    except AllocationError as exc:
        raise BuildError(str(exc)) from exc

    background = resolve_background(concept.background, repo, backgrounds)
    skills = _validate_skills(concept, character_class, background)
    expertise = _validate_expertise(concept, character_class, skills, background)
    languages = _validate_languages(concept, species)
    types = repo.data.proficiency_types
    armor, shield = _armor(concept, repo)
    constitution = ability_modifier(scores.score(Ability.CON))
    hit_points = max(MIN_HIT_POINTS, character_class.hit_die + constitution)

    return CharacterSheet(
        name=concept.name,
        player=concept.player,
        species=species.name,
        character_class=character_class.name,
        level=1,
        background=concept.background,
        abilities=scores,
        proficiencies=Proficiencies(
            saving_throws=list(character_class.saving_throws),
            skills={
                skill: (
                    Proficiency.EXPERTISE
                    if skill.value in expertise
                    else Proficiency.PROFICIENT
                )
                # Background skills are *granted*, not chosen, so they join the class's
                # picks rather than competing with them. Ordered class-first so a sheet
                # reads the way the choices were made.
                for skill in (*skills, *_background_skills(background))
            },
            armor=_class_proficiencies(character_class, _ARMOR, types),
            weapons=_class_proficiencies(character_class, _WEAPONS, types),
            tools={
                name: (
                    Proficiency.EXPERTISE
                    if _normalize(name) in expertise
                    else Proficiency.PROFICIENT
                )
                for name in (
                    *_class_proficiencies(character_class, _TOOLS, types),
                    *(background.tools if background else ()),
                )
            },
            languages=_languages(species, languages, background),
        ),
        hit_points=HitPoints(maximum=hit_points, current=hit_points),
        armor_class=_armor_class(scores, armor, shield),
        speed=species.speed,
        hit_dice=f"1d{character_class.hit_die}",
        inventory=_inventory(concept, armor, shield, background, repo),
        spell_slots=_spell_slots(character_class),
        spells_known=_validate_spells(concept, character_class, repo),
        backstory=concept.backstory or None,
    )


# --- pieces ----------------------------------------------------------------


def grant_issues(
    sheet: CharacterSheet,
    repo: SRDRepository,
    backgrounds: BackgroundLookup | None = None,
) -> list[str]:
    """Ways a finished sheet falls short of what its species and class actually grant.

    The counterpart to `build_character` for sheets that already exist — hand-edited
    ones, and the characters built before the engine enforced choice-points. Reports
    rather than raises: the caller is inspecting a file, not constructing one.
    """
    issues: list[str] = []
    species = repo.species(sheet.species)
    character_class = repo.character_class(sheet.character_class)
    if species is None:
        return [f"no SRD species called {sheet.species!r}"]
    if character_class is None:
        return [f"no SRD class called {sheet.character_class!r}"]

    expected_saves = set(character_class.saving_throws)
    if set(sheet.proficiencies.saving_throws) != expected_saves:
        issues.append(
            f"saving throws should be {', '.join(sorted(a.value for a in expected_saves))}"
        )
    if sheet.speed != species.speed:
        issues.append(f"{species.name} speed is {species.speed}, sheet says {sheet.speed}")
    if sheet.hit_dice != f"{sheet.level}d{character_class.hit_die}":
        issues.append(f"hit dice should be {sheet.level}d{character_class.hit_die}")

    fixed = sum(species.ability_bonuses.values())
    floating = (
        species.ability_bonus_options.choose * species.ability_bonus_options.bonus
        if species.ability_bonus_options is not None
        else 0
    )
    if floating:
        total = sum(sheet.abilities.as_dict().values())
        if total < sum(STANDARD_ARRAY) + fixed + floating:
            options = species.ability_bonus_options
            issues.append(
                f"{species.name} grants +{options.bonus} to {options.choose} abilities of "
                f"your choice and the scores do not include them"
            )

    languages = len(sheet.proficiencies.languages)
    expected_languages = len(species.languages) + (
        species.language_options.choose if species.language_options else 0
    )
    if languages < expected_languages:
        issues.append(
            f"{species.name} knows {len(species.languages)} language(s) and chooses "
            f"{expected_languages - len(species.languages)} more; sheet has {languages}"
        )

    first = character_class.levels.get(1)
    wanted_expertise = first.expertise_choices if first is not None else 0
    if wanted_expertise:
        have = sum(
            1
            for level in (
                *sheet.proficiencies.skills.values(),
                *sheet.proficiencies.tools.values(),
            )
            if level is Proficiency.EXPERTISE
        )
        if have < wanted_expertise:
            issues.append(
                f"{character_class.name} takes expertise in {wanted_expertise} "
                f"proficiencies at level 1; sheet has {have}"
            )

    types = repo.data.proficiency_types
    for field, categories in (("armor", _ARMOR), ("weapons", _WEAPONS), ("tools", _TOOLS)):
        expected = _class_proficiencies(character_class, categories, types)
        # Compared folded, not literally: this exists to check hand-edited sheets, and a
        # human writing "Thieves' Tools" where the index folds to "thieves tools" has the
        # proficiency. Flagging that would train the reader to ignore the validator.
        have = {_normalize(name) for name in getattr(sheet.proficiencies, field)}
        missing = [name for name in expected if _normalize(name) not in have]
        if missing:
            issues.append(f"missing {field} proficiencies: {', '.join(sorted(missing))}")

    # A background the SRD knows grants skills outright. One the SRD has never heard of
    # grants nothing and is not an issue — the table invents most of them, and flagging
    # every character for having a background would train the reader to ignore this list.
    background = resolve_background(sheet.background, repo, backgrounds)
    if background is not None:
        absent = [
            skill.value for skill in background.skills if skill not in sheet.proficiencies.skills
        ]
        if absent:
            issues.append(
                f"{background.name} grants {', '.join(sorted(absent))}; sheet does not have "
                f"{'them' if len(absent) > 1 else 'it'}"
            )
        held_tools = {_normalize(name) for name in sheet.proficiencies.tools}
        missing_tools = [name for name in background.tools if _normalize(name) not in held_tools]
        if missing_tools:
            issues.append(
                f"{background.name} grants {', '.join(sorted(missing_tools))}; sheet does not"
            )
        spoken = {_normalize(name) for name in sheet.proficiencies.languages}
        unspoken = [
            name for name in _background_languages(background) if _normalize(name) not in spoken
        ]
        if unspoken:
            issues.append(
                f"{background.name} teaches {', '.join(sorted(unspoken))}; sheet does not "
                f"list {'them' if len(unspoken) > 1 else 'it'}"
            )
    return issues


def _all_bonuses(concept: Concept, species) -> dict[Ability, int]:
    """Fixed species bonuses plus the floating ones the concept picked.

    Raises when a species offers a choice the concept did not make. The first playtest
    produced a Half-Elf two ability points short because this was silently skipped — a
    quietly wrong sheet is exactly what the deterministic tier exists to prevent, so it
    is now loud.
    """
    bonuses = dict(species.ability_bonuses)
    options = species.ability_bonus_options
    picks = concept.ability_bonus_picks

    if options is None:
        if picks:
            raise BuildError(f"{species.name} has no ability bonuses to choose")
        return bonuses

    allowed = set(options.options)
    if len(set(picks)) != len(picks):
        raise BuildError("the same ability was picked twice for a species bonus")
    if len(picks) != options.choose:
        offered = ", ".join(a.value for a in options.options)
        raise BuildError(
            f"{species.name} grants +{options.bonus} to {options.choose} abilities of "
            f"your choice — pick exactly {options.choose} from: {offered} "
            f"(got {len(picks)})"
        )
    illegal = [a.value for a in picks if a not in allowed]
    if illegal:
        raise BuildError(f"{species.name} cannot raise {', '.join(illegal)}")

    for ability in picks:
        bonuses[ability] = bonuses.get(ability, 0) + options.bonus
    return bonuses


def _validate_expertise(
    concept: Concept, character_class, skills: tuple[Skill, ...], background=None
) -> set[str]:
    """Expertise picks must be things this character is actually proficient in.

    Background grants count. 5e says expertise is "two of your skill proficiencies", not
    two of your class's picks — and now that a background grants two real skills and
    sometimes a tool, excluding them would refuse a legal rogue whose best skill is the
    one her life gave her.
    """
    first = character_class.levels.get(1)
    count = first.expertise_choices if first is not None else 0
    picks = tuple(dict.fromkeys(_normalize(pick) for pick in concept.expertise))

    if not count:
        if picks:
            raise BuildError(f"{character_class.name} has no expertise at level 1")
        return set()

    proficient = (
        {skill.value for skill in skills}
        | {skill.value for skill in _background_skills(background)}
        | {
            _normalize(index)
            for index in character_class.proficiencies
            if index.endswith("-tools")
        }
        | {_normalize(name) for name in (background.tools if background else ())}
    )
    if len(picks) != count:
        raise BuildError(
            f"{character_class.name} takes expertise in exactly {count} of its "
            f"proficiencies at level 1, got {len(picks)}"
        )
    illegal = [pick for pick in picks if pick not in proficient]
    if illegal:
        offered = ", ".join(sorted(proficient))
        raise BuildError(
            f"expertise must be something this character is proficient in — "
            f"{', '.join(illegal)} is not. Available: {offered}"
        )
    return set(picks)


def _validate_languages(concept: Concept, species) -> tuple[str, ...]:
    options = species.language_options
    picks = tuple(dict.fromkeys(_normalize(name) for name in concept.languages))

    if options is None:
        if picks:
            raise BuildError(f"{species.name} grants no extra language to choose")
        return ()

    allowed = {_normalize(index) for index in options.options}
    known = {_normalize(index) for index in species.languages}
    if len(picks) != options.choose:
        raise BuildError(
            f"{species.name} grants {options.choose} extra language(s) of your choice — "
            f"got {len(picks)}"
        )
    for pick in picks:
        if pick in known:
            raise BuildError(f"{pick.replace('_', ' ')} is already known — pick another")
        if pick not in allowed:
            raise BuildError(f"{pick.replace('_', ' ')} is not an SRD language")
    return picks


def _normalize(value: str) -> str:
    """Fold a named proficiency or language to a comparable key.

    Apostrophes go: the SRD index is `thieves-tools` and the GM writes "thieves' tools",
    and those must be the same thing or expertise in one's own tools is unspellable.
    """
    folded = value.strip().casefold().replace("'", "").replace("’", "")
    return re.sub(r"[\s\-]+", "_", folded)


def _validate_skills(concept: Concept, character_class, background=None) -> tuple[Skill, ...]:
    allowed, choose = class_skill_options(character_class)
    chosen = tuple(dict.fromkeys(concept.skills))  # de-duplicate, keep order
    if len(chosen) != len(concept.skills):
        raise BuildError("the same skill was chosen twice")

    # A background grants its skills outright, so a class pick that duplicates one is a
    # wasted choice and the character ends up a proficiency short. 5e's answer is to pick
    # something else, so the engine says so — to the GM, which is where engine objections
    # go (D-005), not to the player.
    granted = set(_background_skills(background))
    clash = [skill.value for skill in chosen if skill in granted]
    if clash:
        spare = sorted(skill.value for skill in allowed if skill not in granted)
        raise BuildError(
            f"{background.name} already grants {', '.join(clash)} — "
            f"choose {len(clash)} other skill(s) from: {', '.join(spare)}"
        )

    illegal = [skill.value for skill in chosen if skill not in allowed]
    if illegal:
        offered = ", ".join(sorted(skill.value for skill in allowed))
        raise BuildError(
            f"{character_class.name} cannot take {', '.join(illegal)} — "
            f"it chooses {choose} from: {offered}"
        )
    if choose and len(chosen) != choose:
        raise BuildError(
            f"{character_class.name} chooses exactly {choose} skills, got {len(chosen)}"
        )
    return chosen


def _armor(concept: Concept, repo: SRDRepository):
    armor = None
    if concept.armor:
        item = repo.equipment(concept.armor)
        if item is None:
            raise BuildError(f"no SRD equipment called {concept.armor!r}")
        if item.armor is None:
            raise BuildError(f"{item.name} is not armor")
        armor = item

    shield = None
    if concept.shield:
        shield = repo.equipment("shield")
        if shield is None:
            raise BuildError("the SRD dataset has no shield — re-run `dndc srd ingest`")
    return armor, shield


def _armor_class(scores: AbilityScores, armor, shield) -> int:
    dexterity = scores.modifier(Ability.DEX)
    if armor is None:
        total = _UNARMORED_BASE_AC + dexterity
    else:
        profile = armor.armor
        bonus = dexterity if profile.dex_bonus else 0
        if profile.max_dex_bonus is not None:
            bonus = min(bonus, profile.max_dex_bonus)
        total = profile.base_ac + bonus
    return total + (_SHIELD_AC if shield is not None else 0)


def _background_skills(background) -> tuple[Skill, ...]:
    return background.skills if background is not None else ()


def _background_languages(background) -> tuple[str, ...]:
    """Languages a background teaches outright — campaign backgrounds only.

    The SRD type has no such field (Acolyte grants two of the character's *choice*, which
    nothing consumes yet — see the handoff), so this reads as empty for an SRD background
    and the two paths stay one code path.
    """
    return tuple(getattr(background, "languages", ()) or ())


def _languages(species, chosen: tuple[str, ...], background) -> list[str]:
    """Everything the character speaks, in the order they came by it.

    De-duplicated rather than refused when a background teaches something the species
    already knows. Unlike the skill clash — where the class *chose* and could have chosen
    otherwise, so a duplicate costs a real pick — a granted language nobody selected costs
    nothing recoverable, and refusing a reusable background because this particular elf
    already speaks Elvish would make it unreusable.
    """
    names: list[str] = []
    seen: set[str] = set()
    for language in (*species.languages, *chosen, *_background_languages(background)):
        key = _normalize(language)
        if key in seen:
            continue
        seen.add(key)
        names.append(_titled(language))
    return names


def resolve_background(name: str | None, repo: SRDRepository, backgrounds=None):
    """The ruleset's background, then the campaign's, then nothing.

    SRD first because the ruleset wins where the two could disagree — and they cannot,
    since `validate_background` refuses a campaign background that reuses an SRD name.
    An unknown name still resolves to `None` and stays flavour, which is what makes every
    character built before backgrounds granted anything still loadable.
    """
    if not name:
        return None
    found = repo.background(name)
    if found is not None:
        return found
    return backgrounds(name) if backgrounds is not None else None


def _inventory(concept: Concept, armor, shield, background, repo: SRDRepository):
    """Everything the character starts carrying, with the weights the SRD gives them.

    Weight used to be zero for everything but armor, which made `carried_weight` a number
    that looked authoritative and was not — and P2.4 inherited the same hole for items
    picked up in play. The repository has the figures; nothing here needs to invent one.
    """
    items = []
    if armor is not None:
        items.append(InventoryItem(name=armor.name, weight=armor.weight, equipped=True))
    if shield is not None:
        items.append(InventoryItem(name=shield.name, weight=shield.weight, equipped=True))

    for name in concept.equipment:
        items.append(_carried(name, repo))
    for granted in (background.equipment if background is not None else ()):
        items.append(_carried(granted.index, repo, quantity=granted.quantity, fallback=granted.name))
    return items


def _carried(key: str, repo: SRDRepository, quantity: int = 1, fallback: str = "") -> InventoryItem:
    """One inventory line, resolved against the SRD where the SRD knows it.

    An unknown name is kept rather than rejected: the GM may hand a character a keepsake
    that is not equipment, and losing it because the SRD has no entry would be the sheet
    contradicting the fiction — the failure P2.4 was built to end. It simply weighs
    nothing, which is honest, because nobody knows what it weighs.
    """
    item = repo.equipment(key)
    if item is None:
        return InventoryItem(name=fallback or key, quantity=quantity)
    return InventoryItem(name=item.name, quantity=quantity, weight=item.weight)


def _spell_slots(character_class) -> dict[int, SpellSlotLevel]:
    first = character_class.levels.get(1)
    if first is None:
        return {}
    return {
        level: SpellSlotLevel(total=total)
        for level, total in first.spell_slots.items()
        if total
    }


def _validate_spells(concept: Concept, character_class, repo: SRDRepository) -> list[str]:
    """Spells must exist, be castable at level 1, and be on this class's list."""
    if not concept.spells:
        return []
    if character_class.spellcasting_ability is None:
        raise BuildError(f"{character_class.name} does not cast spells at level 1")

    known: list[str] = []
    for name in concept.spells:
        spell = repo.spell(name)
        if spell is None:
            raise BuildError(f"no SRD spell called {name!r}")
        if spell.level > 1:
            raise BuildError(f"{spell.name} is level {spell.level} — out of reach at level 1")
        if character_class.index not in spell.classes:
            raise BuildError(f"{spell.name} is not on the {character_class.name} spell list")
        known.append(spell.name)
    return known


def _class_proficiencies(
    character_class, categories: frozenset[str], types: dict[str, str]
) -> list[str]:
    """Class grants in the given SRD categories, as readable names.

    Sorted by what the SRD says each proficiency *is*, not by guessing from its name.
    The previous keyword matching dropped `thieves-tools` — it contains none of the words
    a tools list would have been looking for — and nothing noticed until a rogue reached
    the table without them.

    Saving throws and skills are excluded everywhere: they have their own fields, and
    listing them twice would make the sheet disagree with itself.
    """
    return [
        _titled(index)
        for index in character_class.proficiencies
        if types.get(index, "") in categories
    ]


def _titled(index: str) -> str:
    return index.replace("-", " ").title()
