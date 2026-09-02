"""Validating a background the GM invented (the 2026-08-15 (c) ruling).

The SRD contains exactly one background — Acolyte. Soldier, Sage, Criminal and the rest
are PHB, outside D-007's licence, and must never be ingested. Fable's answer was option 3:
co-creation *proposes* an original background, the engine validates its shape
deterministically, the table confirms, and confirmed ones persist as campaign data.

So this module is the deterministic half of that. It knows nothing about models, tags or
files — it takes the pieces of a proposal and either returns a background the engine is
willing to grant or says exactly why not, in a sentence the GM can act on (D-005: engine
objections go to the GM, never to the player).

**What the shape rules are protecting.** A background is the one place a language model
gets to write *mechanics* rather than fiction, and mechanics are the deterministic tier's
job (D-001). The constraints are the ruling's:

- **exactly two skills**, from the standard list, distinct — what every 5e background
  grants, no more;
- **at most one tool proficiency or one language**, never both — the "small extra";
- **never a numeric bonus.** There is nowhere in the type to put an ability score, so the
  only way one could arrive is written into prose, and prose that says "+1 to Charisma
  checks" is a mechanic the engine did not grant and cannot honour. Refused.

The class-pick clash — a background granting a skill the class also chose, which leaves
the character quietly a proficiency short — needs nothing here: `build_character` already
refuses that, and a campaign background reaches the check by the same path an SRD one
does.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

from dndc.schema.campaign import CampaignBackground, slugify
from dndc.schema.sheet import Skill
from dndc.schema.srd import Background

#: Every 5e background grants two, and this one is not negotiable — a background granting
#: three is a background granting more than the ruleset's own.
BACKGROUND_SKILLS = 2

#: Past this the GM has written a sentence where a name goes.
MAX_NAME_CHARS = 60
MAX_EXTRA_CHARS = 40

#: A signed number anywhere in the prose. Narrow on purpose: it catches the wire form of a
#: mechanical bonus ("+1 to Charisma checks", "-2 on saves"), not every phrasing a model
#: could reach for. The real guarantee is structural — `CampaignBackground` has no field
#: an ability bonus fits in — and this is the guard against one being smuggled through the
#: one field that takes free text.
_NUMERIC_BONUS = re.compile(r"[+\-−–]\s*\d")


class BackgroundError(ValueError):
    """A proposed background the engine will not grant, and why."""


def validate_background(
    *,
    name: str,
    skills: Iterable[str],
    tool: str | None = None,
    language: str | None = None,
    feature: str = "",
    description: str = "",
    srd_names: Iterable[str] = (),
    existing: Mapping[str, CampaignBackground] | None = None,
    languages_known: Iterable[str] = (),
) -> CampaignBackground:
    """Turn a proposal into a grantable background, or raise `BackgroundError`.

    `existing` is the campaign's own book, keyed however the caller likes — names are
    compared folded. A proposal that matches an existing background exactly comes back
    unchanged (the GM re-declaring what the campaign already has is reuse, not a clash);
    one that reuses a name for different mechanics is refused, because a name that means
    two things is a name the sheet cannot resolve.
    """
    clean_name = " ".join(name.split())
    if not clean_name:
        raise BackgroundError("the background has no name")
    if len(clean_name) > MAX_NAME_CHARS:
        raise BackgroundError(
            f"the background name is {len(clean_name)} characters — it should be a name, "
            f"not a sentence (max {MAX_NAME_CHARS})"
        )

    for label, text in (("name", clean_name), ("feature", feature), ("description", description)):
        if _NUMERIC_BONUS.search(text):
            raise BackgroundError(
                f"the {label} carries a numeric bonus. A background grants two skills and "
                "at most one tool or language — never a bonus to a score, a roll or a "
                "number of any kind. Describe what the character knows, not what it adds."
            )

    folded = clean_name.casefold()
    for srd_name in srd_names:
        if srd_name.casefold() == folded:
            raise BackgroundError(
                f"the ruleset already has a background called {srd_name} — use that one by "
                f"name, or call this one something else"
            )

    granted = _skills(skills)
    tool_name, language_name = _extra(tool, language, languages_known)

    try:
        index = slugify(clean_name)
    except ValueError as exc:
        # A "name" of nothing but punctuation. Reported as an objection rather than
        # crashing the interview, like every other malformed proposal.
        raise BackgroundError(f"{clean_name!r} is not a usable background name") from exc

    candidate = CampaignBackground(
        index=index,
        name=clean_name,
        skills=granted,
        tools=(tool_name,) if tool_name else (),
        languages=(language_name,) if language_name else (),
        feature=" ".join(feature.split()),
        feature_description=(" ".join(description.split()),) if description.strip() else (),
    )

    for held in (existing or {}).values():
        if held.name.casefold() != folded:
            continue
        if _grants(held) == _grants(candidate):
            # The same background, declared again. Reuse rather than a collision: the GM
            # re-stating what the campaign already carries is the behaviour we want, and
            # returning the stored row keeps its original provenance.
            return held
        raise BackgroundError(
            f"this campaign already has a background called {held.name}, granting "
            f"{describe_grants(held)}. Use it as it stands, or name this one differently."
        )

    return candidate


def describe_grants(background: Background) -> str:
    """One line of what a background gives, for a confirmation prompt or an objection.

    Takes the SRD type as well as the campaign one — the prompt lists both in the same
    menu, and a reader should not have to know which side of D-007 a row came from.
    """
    parts = [", ".join(skill.value.replace("_", " ") for skill in background.skills)]
    parts.extend(background.tools)
    parts.extend(f"{language} (language)" for language in _granted_languages(background))
    if background.languages_choose:
        parts.append(f"{background.languages_choose} language(s) of your choice")
    return "; ".join(part for part in parts if part)


def _granted_languages(background: Background) -> tuple[str, ...]:
    """Named languages — campaign backgrounds only; the SRD type has no such field."""
    return tuple(getattr(background, "languages", ()) or ())


def _grants(background: CampaignBackground) -> tuple:
    """What two backgrounds have to share to be the same background. Flavour is not it."""
    return (
        tuple(sorted(skill.value for skill in background.skills)),
        tuple(sorted(_normalize(name) for name in background.tools)),
        tuple(sorted(_normalize(name) for name in _granted_languages(background))),
    )


def _skills(skills: Iterable[str]) -> tuple[Skill, ...]:
    parsed: list[Skill] = []
    for token in skills:
        name = _normalize(token)
        try:
            skill = Skill(name)
        except ValueError as exc:
            offered = ", ".join(sorted(s.value.replace("_", " ") for s in Skill))
            raise BackgroundError(
                f"{token.strip()!r} is not a skill. Choose from: {offered}"
            ) from exc
        if skill in parsed:
            raise BackgroundError(
                f"{skill.value.replace('_', ' ')} is listed twice — a background grants "
                f"{BACKGROUND_SKILLS} different skills"
            )
        parsed.append(skill)

    if len(parsed) != BACKGROUND_SKILLS:
        listed = ", ".join(skill.value.replace("_", " ") for skill in parsed) or "none"
        raise BackgroundError(
            f"a background grants exactly {BACKGROUND_SKILLS} skills, got {len(parsed)}: "
            f"{listed}"
        )
    return tuple(parsed)


def _extra(
    tool: str | None, language: str | None, languages_known: Iterable[str]
) -> tuple[str | None, str | None]:
    """The one small extra, or none. A tool *or* a language, never both."""
    tool_name = " ".join(tool.split()) if tool else ""
    language_name = " ".join(language.split()) if language else ""

    if tool_name and language_name:
        raise BackgroundError(
            f"a background grants one tool *or* one language, not both — got "
            f"{tool_name!r} and {language_name!r}. Drop whichever matters less."
        )
    for label, value in (("tool", tool_name), ("language", language_name)):
        if len(value) > MAX_EXTRA_CHARS:
            raise BackgroundError(
                f"the {label} is {len(value)} characters — name one thing (max "
                f"{MAX_EXTRA_CHARS})"
            )

    if language_name:
        known = {_normalize(name) for name in languages_known}
        # Checked only when the caller supplied the ruleset's languages — a pure function
        # cannot know them, and validating against an empty set would refuse everything.
        if known and _normalize(language_name) not in known:
            offered = ", ".join(sorted(name.replace("_", " ") for name in known))
            raise BackgroundError(
                f"{language_name} is not a language in this ruleset. Choose from: {offered}"
            )
    return tool_name or None, language_name or None


def _normalize(value: str) -> str:
    """Fold a name to a comparable key — the same folding `rules/build.py` uses."""
    folded = value.strip().casefold().replace("'", "").replace("’", "")
    return re.sub(r"[\s\-]+", "_", folded)
