"""Prompt templates as files, plus a deliberately dumb renderer.

CLAUDE.md requires prompts to live in `gm/prompts/` as templates rather than inline
strings — a prompt change is design-relevant, and it should show up in a diff as prose,
not buried in Python.

The renderer substitutes `{{ name }}` and nothing else. No conditionals, no loops, no
expressions: every decision about *what* goes in a section is made in Python, where it
is testable, and the template decides only *where* it lands. `str.format` was rejected
because prompt prose is full of literal braces (dice notation, JSON examples), and
`string.Template`'s `$name` collides with dollar amounts.

Substitution is strict in both directions. A placeholder with no value raises, and a
value with no placeholder raises — the second is the one that matters, because that is
the shape of "the canon ledger silently stopped reaching the prompt after a rename".
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")
#: Three or more newlines collapse to two, so an empty section leaves no ragged gap.
_BLANK_RUN = re.compile(r"\n{3,}")


class TemplateError(RuntimeError):
    """A template could not be found, or was rendered with the wrong values."""


@lru_cache(maxsize=None)
def load_template(name: str) -> str:
    """Read `gm/prompts/<name>.md`. Cached — templates do not change at runtime."""
    path = PROMPTS_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        available = ", ".join(sorted(p.stem for p in PROMPTS_DIR.glob("*.md")))
        raise TemplateError(f"no template named {name!r} (have: {available})") from exc


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def render(template: str, /, **values: object) -> str:
    """Substitute `{{ name }}`. Raises on a missing placeholder or an unused value."""
    wanted = placeholders(template)
    given = set(values)

    if missing := wanted - given:
        raise TemplateError(f"template needs values for: {', '.join(sorted(missing))}")
    if unused := given - wanted:
        raise TemplateError(f"no placeholder for: {', '.join(sorted(unused))}")

    rendered = _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)
    return _BLANK_RUN.sub("\n\n", rendered).strip()


def render_template(name: str, /, **values: object) -> str:
    return render(load_template(name), **values)
