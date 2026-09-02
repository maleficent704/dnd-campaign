"""Parsing the GM's `[[BACKGROUND: ...]]` tag (the 2026-08-15 (c) ruling).

The seventh use of the `[[TAG:]]` convention `[[CHECK]]` established, specified in D-008
item 15:

    [[BACKGROUND:
    name: Salt-Road Grifter
    skills: deception, sleight of hand
    tool: forgery kit
    feature: Known Face on the Road
    description: You have run the coast road long enough to know which inns ask questions.
    ]]

`tool:` may instead be `language:`, and at most one of the two may appear — that is the
"small extra" the ruling allows. There is no `equipment:` key: starting gear already has a
home in `[[PROPOSE:]]`, where it is validated against the SRD catalogue, and a second
unvalidated path into the inventory is how a background starts granting a longbow.

**The posture is `[[CHECK]]`'s, not `[[CANON]]`'s.** The canon parser bends over backwards
never to lose a fact. This one refuses anything it cannot read cleanly and hands the
objection back to the GM (D-005), because a half-read background grants a proficiency
nobody chose — and unlike a dropped canon line, that lands on a character sheet.

Parsing only. What a background may *grant* is `rules/background.py`, which is where the
ruling's shape rules live and which knows nothing about tags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.rules.background import BackgroundError

BACKGROUND_PATTERN = re.compile(
    r"\[\[\s*BACKGROUND\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)

#: Keys the parser understands. A `key:` outside this set continues the previous field,
#: which is what keeps `description: She left Kelmore: a mining town` in one piece.
_KEY_ALIASES = {
    "title": "name",
    "background": "name",
    "skill": "skills",
    "proficiencies": "skills",
    "tools": "tool",
    "tool_proficiency": "tool",
    "kit": "tool",
    "languages": "language",
    "feature_name": "feature",
    "feature_description": "description",
    "flavour": "description",
    "flavor": "description",
    "text": "description",
    "summary": "description",
}

_KNOWN_KEYS = frozenset({"name", "skills", "tool", "language", "feature", "description"})

#: Keys that name something a background is not allowed to grant. Refused by name rather
#: than ignored: a silently dropped `equipment:` line is the GM telling the player about
#: gear the sheet never received, which is the fiction/state divergence P2.4 exists to end.
_REFUSED_KEYS = {
    "equipment": "backgrounds grant no equipment — put starting gear in the "
                 "[[PROPOSE:]] block, where the engine can check it against the ruleset",
    "gear": "backgrounds grant no equipment — put starting gear in the [[PROPOSE:]] block",
    "items": "backgrounds grant no equipment — put starting gear in the [[PROPOSE:]] block",
    "money": "backgrounds grant no starting money",
    "gold": "backgrounds grant no starting money",
    "ability": "backgrounds never touch ability scores",
    "abilities": "backgrounds never touch ability scores",
    "ability_bonuses": "backgrounds never touch ability scores",
    "bonus": "backgrounds grant no bonuses of any kind",
    "bonuses": "backgrounds grant no bonuses of any kind",
    "hp": "backgrounds never touch hit points",
    "hit_points": "backgrounds never touch hit points",
    "spells": "backgrounds grant no spells",
    "expertise": "backgrounds grant proficiency, never expertise — expertise is the "
                 "class's, and goes in the [[PROPOSE:]] block",
}

_LIST_SPLIT = re.compile(r"[,;]|\band\b", re.IGNORECASE)

#: Words a GM writes in a `language:` field meaning "one of the player's choice". The
#: ruling's extra is a language the background *teaches*, so a background has to say which.
_UNNAMED_LANGUAGE = re.compile(
    r"^(?:yes|one|1|any|a language|one language|.*of (?:your|their) choice.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BackgroundTag:
    """One background the GM proposed, as written. Nothing is validated yet."""

    name: str
    skills: tuple[str, ...]
    tool: str | None = None
    language: str | None = None
    feature: str = ""
    description: str = ""
    raw: str = ""


def find_background(text: str) -> BackgroundTag | None:
    """The last background in a GM reply, or None if it proposed none.

    Last rather than first, for the same reason `find_proposal` takes the last proposal:
    if the GM revises inside one reply, the revision is the one it means.
    """
    matches = list(BACKGROUND_PATTERN.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    return _parse_body(match.group("body"), raw=match.group(0))


def strip_background_tags(text: str) -> str:
    """The reply without the tag — what the player reads."""
    stripped = BACKGROUND_PATTERN.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def _parse_body(body: str, raw: str) -> BackgroundTag:
    fields = _key_values(body, raw=raw)

    missing = [key for key in ("name", "skills") if not fields.get(key)]
    if missing:
        raise BackgroundError(
            f"the background proposal is missing: {', '.join(missing)}"
        )

    language = fields.get("language", "").strip()
    if language and _UNNAMED_LANGUAGE.fullmatch(language):
        raise BackgroundError(
            "a background teaches a specific language — name it (or drop the line), "
            "rather than granting a choice the character then has to remember to spend"
        )

    return BackgroundTag(
        name=fields["name"],
        skills=tuple(token.strip() for token in _split(fields["skills"]) if token.strip()),
        tool=fields.get("tool") or None,
        language=language or None,
        feature=fields.get("feature", ""),
        description=fields.get("description", ""),
        raw=raw,
    )


def _key_values(body: str, raw: str) -> dict[str, str]:
    """`key: value` lines, one per field — the `[[PROPOSE:]]` parser's rule.

    A line only starts a new field if its key is one the parser knows; anything else
    continues the previous value. That is what keeps a wrapped description whole, and it
    is the reason a refused key has to be caught here rather than left to fall through as
    prose.
    """
    fields: dict[str, str] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if not stripped:
            continue

        key, separator, value = stripped.partition(":")
        normalized = key.strip().casefold().replace("-", "_").replace(" ", "_")
        normalized = _KEY_ALIASES.get(normalized, normalized)

        if separator and normalized in _REFUSED_KEYS:
            raise BackgroundError(_REFUSED_KEYS[normalized])
        if separator and normalized in _KNOWN_KEYS:
            fields[normalized] = value.strip()
            current = normalized
        elif current is not None:
            fields[current] = f"{fields[current]} {stripped}".strip()
        else:
            raise BackgroundError(
                f"background line is not a known `key: value`: {stripped!r}"
            )

    if not fields:
        raise BackgroundError("the background proposal is empty")
    return fields


def _split(value: str) -> list[str]:
    parts: list[str] = []
    for line in value.splitlines():
        parts.extend(_LIST_SPLIT.split(line))
    return [part for part in parts if part.strip()]
