"""Parsing the GM's co-creation tags (P1.4).

Two tags, both specified in `prompts/creation_core.md`:

    [[PROPOSE:
    name: Brannoc Thorn
    species: Human
    class: Fighter
    priority: str, con, dex, wis, cha, int
    skills: athletics, intimidation
    ]]

    [[FACT: Brannoc's older brother died at the siege of Kelmore.]]

`PROPOSE` is the character; `FACT` is one line of backstory bound for the canon ledger.

Same posture as `checkrequest.py`, for the same reason: forgiving about surface form
(key casing, `class` vs `character_class`, `Dexterity` vs `dex`, commas or newlines
between skills) because the producer is a language model, and strict about meaning
(an unknown ability, a missing name, a skill the engine does not recognise all raise
rather than being quietly dropped — a silently discarded proficiency is a character
that is wrong in a way nobody notices until it matters).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.rules.build import (
    DEFAULT_SHAPE,
    POINT_BUY_METHOD,
    STANDARD_ARRAY_METHOD,
    Concept,
)
from dndc.schema.sheet import Ability, Skill

PROPOSE_PATTERN = re.compile(r"\[\[\s*PROPOSE\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)
FACT_PATTERN = re.compile(r"\[\[\s*FACT\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)

#: Both tags at once, for stripping machine instruction out of what players read.
_ANY_TAG = re.compile(
    r"\[\[\s*(?:PROPOSE|FACT)\s*:.*?\]\]", re.IGNORECASE | re.DOTALL
)

#: A fence with nothing left in it — what a stripped tag leaves behind.
_EMPTY_FENCE = re.compile(r"```[a-z]*[ \t]*\n?\s*```", re.IGNORECASE)

_ABILITY_WORDS: dict[str, Ability] = {
    "strength": Ability.STR, "str": Ability.STR,
    "dexterity": Ability.DEX, "dex": Ability.DEX,
    "constitution": Ability.CON, "con": Ability.CON,
    "intelligence": Ability.INT, "int": Ability.INT,
    "wisdom": Ability.WIS, "wis": Ability.WIS,
    "charisma": Ability.CHA, "cha": Ability.CHA,
}

#: Keys the GM might reach for, mapped to the one the parser uses.
_KEY_ALIASES = {
    "character_class": "class",
    "character class": "class",
    "klass": "class",
    "race": "species",
    "ability_priority": "priority",
    "abilities": "priority",
    "ability priority": "priority",
    "skill": "skills",
    "proficiencies": "skills",
    "spell": "spells",
    "ability_bonus": "ability_bonuses",
    "bonuses": "ability_bonuses",
    "ability_bonus_picks": "ability_bonuses",
    "language": "languages",
    "extra_languages": "languages",
    "gear": "equipment",
    "items": "equipment",
    "allocation": "method",
    "backstory_summary": "backstory",
    "pronoun": "pronouns",
    "gender": "pronouns",
}

_REQUIRED = ("name", "species", "class", "priority")

#: Every field the parser understands. A `key:` outside this set is prose, not a field.
_KNOWN_KEYS = frozenset(
    {*_REQUIRED, "skills", "background", "method", "shape", "armor", "shield",
     "equipment", "spells", "backstory", "ability_bonuses", "expertise", "languages",
     "pronouns"}
)

_TRUE = {"yes", "true", "y", "1", "shield"}
_FALSE = {"no", "false", "n", "0", "none", ""}

_LIST_SPLIT = re.compile(r"[,;]|\band\b", re.IGNORECASE)

#: Words that can sit inside an ability ranking without meaning anything — list glue and
#: the tails of ordinals ("1st", "2nd"). Anything else unrecognised is an error, so a
#: misspelled ability is reported rather than silently shortening the ranking.
_PRIORITY_NOISE = frozenset({"and", "then", "st", "nd", "rd", "th"})


class ProposalError(ValueError):
    """The GM proposed a character in a form the engine cannot act on."""


@dataclass(frozen=True)
class Proposal:
    """A parsed `[[PROPOSE: ...]]`, plus the raw tag for the log."""

    concept: Concept
    raw: str


def find_proposal(text: str, player: str) -> Proposal | None:
    """The last proposal in a GM reply, or None if it was still interviewing.

    Last rather than first: if the GM revises within one reply, the revision is the one
    it means.
    """
    matches = list(PROPOSE_PATTERN.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    return Proposal(
        concept=_parse_body(match.group("body"), player=player, raw=match.group(0)),
        raw=match.group(0),
    )


def find_facts(text: str) -> list[str]:
    """Backstory facts, in the order the GM wrote them."""
    facts = []
    for match in FACT_PATTERN.finditer(text):
        fact = " ".join(match.group("body").split())
        if fact:
            facts.append(fact)
    return facts


def strip_tags(text: str) -> str:
    """The conversation without the machine instruction — what a player should read.

    Empty code fences are cleaned up afterwards because the GM tends to wrap the tag in
    one: removing the tag then leaves a bare ``` ``` sitting in the middle of the reply,
    which is exactly the kind of machine residue the players should never see.
    """
    stripped = _EMPTY_FENCE.sub("", _ANY_TAG.sub("", text))
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


# --- parsing ---------------------------------------------------------------


def _parse_body(body: str, player: str, raw: str) -> Concept:
    fields = _key_values(body, raw=raw)

    missing = [key for key in _REQUIRED if not fields.get(key)]
    if missing:
        raise ProposalError(f"proposal is missing: {', '.join(missing)}")

    method = _method(fields.get("method", ""), raw=raw)
    return Concept(
        name=fields["name"],
        player=player,
        species=fields["species"],
        character_class=fields["class"],
        priority=_priority(fields["priority"], raw=raw),
        skills=_skills(fields.get("skills", ""), raw=raw),
        ability_bonus_picks=_abilities(fields.get("ability_bonuses", "")),
        expertise=_items(fields.get("expertise", "")),
        languages=_items(fields.get("languages", "")),
        background=fields.get("background") or None,
        method=method,
        shape=_shape(fields.get("shape", "")),
        armor=fields.get("armor") or None,
        shield=_flag(fields.get("shield", "")),
        equipment=_items(fields.get("equipment", "")),
        spells=_items(fields.get("spells", "")),
        backstory=fields.get("backstory", ""),
        pronouns=fields.get("pronouns", ""),
    )


def _key_values(body: str, raw: str) -> dict[str, str]:
    """`key: value` lines, one per field.

    A line only starts a new field if its key is one the parser knows. Anything else
    continues the previous value — which is what makes `backstory: He left Kelmore: a
    mining town` parse as one sentence rather than an unknown `Kelmore` field, and what
    keeps a wrapped backstory from losing its second half silently.
    """
    fields: dict[str, str] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if not stripped:
            continue

        key, separator, value = stripped.partition(":")
        normalized = key.strip().casefold().replace("-", "_")
        normalized = _KEY_ALIASES.get(normalized, normalized)

        if separator and normalized in _KNOWN_KEYS:
            fields[normalized] = value.strip()
            current = normalized
        elif current is not None:
            fields[current] = f"{fields[current]} {stripped}".strip()
        else:
            raise ProposalError(f"proposal line is not a known `key: value`: {stripped!r}")

    if not fields:
        raise ProposalError(f"proposal is empty: {raw!r}")
    return fields


def _priority(value: str, raw: str) -> tuple[Ability, ...]:
    """An ordering of all six abilities, best first.

    Read as a stream of words rather than split on commas, because the separators the GM
    actually uses vary — `str, dex, con`, `1. str 2. dex`, a line break mid-list, a
    trailing `and`. Word order is the only thing that carries meaning here, so that is
    the only thing this depends on.
    """
    order: list[Ability] = []
    for word in re.findall(r"[a-z]+", value.casefold()):
        ability = _ABILITY_WORDS.get(word)
        if ability is None:
            if word in _PRIORITY_NOISE:
                continue
            raise ProposalError(f"unknown ability in priority: {word!r}")
        if ability in order:
            raise ProposalError(f"{ability.value} listed twice in the ability priority")
        order.append(ability)

    if len(order) != len(Ability):
        listed = ", ".join(a.value for a in order)
        raise ProposalError(
            f"ability priority must rank all six abilities, got {len(order)}: {listed}"
        )
    return tuple(order)


def _abilities(value: str) -> tuple[Ability, ...]:
    """A plain list of abilities — the species' floating bonus picks."""
    picks: list[Ability] = []
    for word in re.findall(r"[a-z]+", value.casefold()):
        ability = _ABILITY_WORDS.get(word)
        if ability is None:
            if word in _PRIORITY_NOISE:
                continue
            raise ProposalError(f"unknown ability in ability_bonuses: {word!r}")
        picks.append(ability)
    return tuple(picks)


def _skills(value: str, raw: str) -> tuple[Skill, ...]:
    skills: list[Skill] = []
    for token in _split(value):
        name = token.strip().casefold().replace(" ", "_").replace("-", "_")
        try:
            skills.append(Skill(name))
        except ValueError as exc:
            raise ProposalError(f"unknown skill: {token.strip()!r}") from exc
    return tuple(skills)


def _method(value: str, raw: str) -> str:
    normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
    if not normalized:
        return STANDARD_ARRAY_METHOD
    if "point" in normalized:
        return POINT_BUY_METHOD
    if "array" in normalized or "standard" in normalized:
        return STANDARD_ARRAY_METHOD
    raise ProposalError(f"unknown allocation method: {value.strip()!r}")


def _shape(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized or DEFAULT_SHAPE


def _flag(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    # Anything else in a shield field is a shield being named, e.g. "a wooden shield".
    return True


def _items(value: str) -> tuple[str, ...]:
    return tuple(token.strip() for token in _split(value) if token.strip())


def _split(value: str) -> list[str]:
    parts: list[str] = []
    for line in value.splitlines():
        parts.extend(_LIST_SPLIT.split(line))
    return [part for part in parts if part.strip()]
