"""Prompt assembly for guided character co-creation (P1.4, D-005).

Separate from `gm/context.py` because it is a different job with a different contract:
play narrates a world that already exists, creation builds one character and then stops.

Two ways this prompt deliberately differs from the play prompt:

**The conversation accumulates.** D-002 forbids a growing transcript for *play*, because
a campaign runs for dozens of sessions and an unbounded prompt is unbounded cost. A
creation interview is a dozen exchanges, ends, and is thrown away — and it genuinely
needs its own history, since a backstory built on turn nine has to remember turn two.
The bound here is the interview itself.

**The SRD menu is injected, not recalled.** The GM is shown exactly which species and
classes exist and how many skills each class picks, so an option that does not exist is
never offered to a player in the first place. The engine still validates; this is what
keeps the validation from ever having to fire in front of someone.
"""

from __future__ import annotations

from typing import Sequence

from dndc.gm.templates import render_template
from dndc.models.base import DEFAULT_MAX_TOKENS, GMRequest, Message, Role
from dndc.rules.build import class_skill_options
from dndc.schema.sheet import CharacterSheet
from dndc.srd.repository import SRDRepository

#: Armour categories worth offering at level 1, in the order a player thinks of them.
_ARMOR_CATEGORIES = ("Light", "Medium", "Heavy")


def render_options(repo: SRDRepository) -> str:
    """The SRD menu, as prompt text. Session-stable, so it rides in the cached prefix."""
    species = sorted(record.name for record in repo.data.species.values())
    lines = [
        "## What this ruleset actually offers",
        "",
        "Offer nothing outside these lists.",
        "",
        f"**Species:** {', '.join(species)}",
        "",
        "**Classes**, with the skills each one may choose from:",
    ]

    for character_class in sorted(repo.data.classes.values(), key=lambda c: c.name):
        allowed, choose = class_skill_options(character_class)
        if not allowed:
            continue
        skills = ", ".join(sorted(skill.value.replace("_", " ") for skill in allowed))
        caster = (
            " *(spellcaster)*" if character_class.spellcasting_ability is not None else ""
        )
        lines.append(f"- **{character_class.name}**{caster} — choose {choose} from: {skills}")

    armor = _armor_by_category(repo)
    if armor:
        lines.extend(["", "**Armour:**"])
        lines.extend(f"- {category}: {names}" for category, names in armor)

    lines.extend([
        "",
        "Spells are not listed — name them from the class's own SRD list and the engine "
        "will check them.",
    ])
    return "\n".join(lines)


def _armor_by_category(repo: SRDRepository) -> list[tuple[str, str]]:
    grouped: dict[str, list[str]] = {}
    for item in repo.data.equipment.values():
        if item.armor is None:
            continue
        grouped.setdefault(item.armor.category, []).append(item.name)
    return [
        (category, ", ".join(sorted(grouped[category])))
        for category in _ARMOR_CATEGORIES
        if category in grouped
    ]


class CreationPromptBuilder:
    """Builds the request for one exchange of the interview."""

    def __init__(self, repo: SRDRepository) -> None:
        self.repo = repo
        self._options = render_options(repo)

    def system(self) -> str:
        """Instructions plus the SRD menu. Fixed for the interview — the cached prefix."""
        return render_template("creation_core", options=self._options)

    def draft_state(self, sheet: CharacterSheet | None, facts: Sequence[str]) -> str:
        """What has been built so far. Volatile, so it sits outside the cache breakpoint."""
        if sheet is None and not facts:
            return ""

        lines = ["## Built so far"]
        if sheet is not None:
            lines.append(
                f"\nThe engine has built and validated **{sheet.name}** — a level "
                f"{sheet.level} {sheet.species} {sheet.character_class}"
                + (f" ({sheet.background})" if sheet.background else "")
                + ". The player can see the full sheet; you do not need to recite it, and "
                "must not quote numbers from it. To change it, propose again in full."
            )
        if facts:
            lines.append("\nBackstory recorded so far:")
            lines.extend(f"- {fact}" for fact in facts)
        return "\n".join(lines)

    def build(
        self,
        messages: Sequence[Message],
        sheet: CharacterSheet | None = None,
        facts: Sequence[str] = (),
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        call_id: str | None = None,
    ) -> GMRequest:
        return GMRequest(
            system=self.system(),
            system_volatile=self.draft_state(sheet, facts),
            messages=tuple(messages),
            model=model,
            max_tokens=max_tokens,
            call_id=call_id,
        )


def user(text: str) -> Message:
    return Message(role=Role.USER, content=text)


def assistant(text: str) -> Message:
    return Message(role=Role.ASSISTANT, content=text)
