"""Parsing the GM's `[[CHECK: ...]]` request (P1.2's convention, P1.3's consumer).

D-001's boundary rule: the GM may *request* a mechanical resolution but the engine
computes it. `system_core.md` specifies the exact form the request takes:

    [[CHECK: <ability or skill> DC <number> — <what happens on a failure>]]

This module turns that back into structured data. It is deliberately forgiving about
surface form — dash style, capitalisation, `DC15` vs `DC 15`, a bare skill name versus
`Dexterity (Stealth)` — because the producer is a language model and rejecting a turn
over an en dash would be a bad trade. It is *not* forgiving about the parts that carry
meaning: an unrecognised ability or a missing DC raises, rather than guessing a DC and
silently inventing the difficulty the GM was supposed to set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.schema.sheet import SKILL_ABILITY, Ability, Skill

#: The whole tag. Non-greedy body so two requests in one reply parse as two.
CHECK_PATTERN = re.compile(r"\[\[\s*CHECK\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)

#: `DC 15`, `DC15`, `dc: 15`.
_DC_PATTERN = re.compile(r"\bDC\s*:?\s*(?P<dc>\d{1,2})\b", re.IGNORECASE)

#: Any dash, plus a couple of written alternatives, separating stakes from the terms.
_STAKES_SPLIT = re.compile(r"\s*(?:[—–-]|\bon failure\b|\bif they fail\b)\s*", re.IGNORECASE)

#: Full ability names and the abbreviations the model might reach for.
_ABILITY_WORDS: dict[str, Ability] = {
    "strength": Ability.STR, "str": Ability.STR,
    "dexterity": Ability.DEX, "dex": Ability.DEX,
    "constitution": Ability.CON, "con": Ability.CON,
    "intelligence": Ability.INT, "int": Ability.INT,
    "wisdom": Ability.WIS, "wis": Ability.WIS,
    "charisma": Ability.CHA, "cha": Ability.CHA,
}

#: Skill names as prose ("sleight of hand" -> SLEIGHT_OF_HAND).
_SKILL_WORDS: dict[str, Skill] = {skill.value.replace("_", " "): skill for skill in Skill}

_WORD = re.compile(r"[a-z]+(?: [a-z]+)*")


class CheckRequestError(ValueError):
    """The GM asked for a check in a form the engine cannot act on."""


@dataclass(frozen=True)
class CheckRequest:
    """A resolution the GM asked for, ready to hand to `rules/checks.py`."""

    ability: Ability
    dc: int
    skill: Skill | None = None
    stakes: str = ""
    #: Whether the GM said "save" rather than "check" — different proficiency rules.
    is_save: bool = False
    raw: str = ""

    @property
    def label(self) -> str:
        if self.skill is not None:
            return f"{self.ability.value.upper()} ({self.skill.value.replace('_', ' ')})"
        return self.ability.value.upper()


def find_check_request(text: str) -> CheckRequest | None:
    """The first check request in a GM reply, or None if it just narrated."""
    requests = find_check_requests(text)
    return requests[0] if requests else None


def find_check_requests(text: str) -> list[CheckRequest]:
    return [_parse_body(match.group("body"), raw=match.group(0)) for match in CHECK_PATTERN.finditer(text)]


def strip_check_requests(text: str) -> str:
    """The narration without the tag, for display and for the recent window.

    The raw tag is machine instruction, not prose; leaving it in would put a literal
    `[[CHECK: ...]]` in the transcript the GM later reads back as its own past voice.
    """
    return _tidy(CHECK_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_body(body: str, raw: str) -> CheckRequest:
    dc_match = _DC_PATTERN.search(body)
    if dc_match is None:
        raise CheckRequestError(f"check request has no DC: {raw!r}")
    dc = int(dc_match.group("dc"))

    terms = body[: dc_match.start()]
    remainder = body[dc_match.end():]
    stakes = _STAKES_SPLIT.sub("", remainder, count=1).strip() if remainder.strip() else ""

    ability, skill = _parse_terms(terms, raw=raw)
    return CheckRequest(
        ability=ability,
        skill=skill,
        dc=dc,
        stakes=stakes,
        is_save="sav" in body.lower(),
        raw=raw,
    )


def _parse_terms(terms: str, raw: str) -> tuple[Ability, Skill | None]:
    """Read `Dexterity (Stealth)`, `Stealth`, `Dex`, or `Strength` out of the terms."""
    lowered = terms.lower()
    found_skill: Skill | None = None
    found_ability: Ability | None = None

    for phrase in _WORD.findall(lowered):
        # Longest match first: "sleight of hand" must beat "hand".
        for candidate in sorted(_SKILL_WORDS, key=len, reverse=True):
            if candidate in phrase and found_skill is None:
                found_skill = _SKILL_WORDS[candidate]
                break
        for word in phrase.split():
            if word in _ABILITY_WORDS and found_ability is None:
                found_ability = _ABILITY_WORDS[word]

    if found_skill is not None:
        # The skill's governing ability is fixed by the SRD; if the GM named a different
        # one, the SRD wins — that mapping is rules data, not a judgment call.
        return SKILL_ABILITY[found_skill], found_skill
    if found_ability is not None:
        return found_ability, None

    raise CheckRequestError(f"check request names no ability or skill the engine knows: {raw!r}")
