"""Assembling the GM prompt (P1.2).

D-002's prompt rule: the GM prompt is **rebuilt every turn** from ledger + chronicle +
recent window, never from a growing transcript. That is what bounds cost across a
campaign of dozens of sessions, and it is why this module exists as a builder rather than
a conversation object that accumulates.

The assembled request has three parts, ordered by how often they change:

1. `system` — GM instructions plus the D-006 scaffolding directive. Fixed for a session,
   so it carries the cache breakpoint.
2. `system_volatile` — campaign, party, scene, canon. Changes as play proceeds.
3. `messages` — the recent window of turns, then this turn's player input with any
   engine results attached.

Engine results ride with the player input rather than in campaign state because they are
turn-scoped: they describe what just happened, not what is true. That placement is also
what D-001 describes — the engine resolves, then hands the outcome to the GM to narrate.

The chronicle layer (D-002's third memory tier) is not built here; Phase 2 owns it. The
recent window is the whole of the middle memory tier for now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from dndc.gm.canon import CanonEntry, CanonLedger, render_entries
from dndc.gm.templates import render_template
from dndc.models.base import DEFAULT_MAX_TOKENS, GMRequest, Message, Role
from dndc.schema.sheet import CharacterSheet

#: Filenames in `gm/prompts/`, keyed by the config's `gameplay.scaffolding` (D-006).
SCAFFOLDING_TEMPLATES = {
    "high": "scaffolding_high",
    "low": "scaffolding_low",
    "off": "scaffolding_off",
}

#: How many past turns ride along by default. Each turn is two messages.
DEFAULT_WINDOW = 6

_NO_RESOLUTIONS = "(none — nothing needed resolving this turn)"
_NO_PARTY = "(no characters created yet)"
_NO_SCENE = "(the campaign has not opened yet — establish an opening scene)"


@dataclass(frozen=True)
class PartyMember:
    """What the GM needs to know about a character: identity, and current condition.

    Deliberately not the whole sheet. The GM narrates; it does not need proficiency
    bonuses or an inventory manifest to do that, and every token spent here is spent
    every single turn.
    """

    name: str
    player: str
    descriptor: str = ""
    hp_current: int | None = None
    hp_max: int | None = None
    conditions: tuple[str, ...] = ()

    @classmethod
    def from_sheet(cls, sheet: CharacterSheet) -> PartyMember:
        return cls(
            name=sheet.name,
            player=sheet.player,
            descriptor=f"level {sheet.level} {sheet.species} {sheet.character_class}",
            hp_current=sheet.hit_points.current,
            hp_max=sheet.hit_points.maximum,
        )

    def render(self) -> str:
        parts = [f"- **{self.name}** (played by {self.player})"]
        if self.descriptor:
            parts.append(f", {self.descriptor}")
        if self.hp_current is not None and self.hp_max is not None:
            parts.append(f" — {self.hp_current}/{self.hp_max} HP")
            if self.hp_current == 0:
                parts.append(" (unconscious)")
        if self.conditions:
            parts.append(f" [{', '.join(self.conditions)}]")
        return "".join(parts)


@dataclass(frozen=True)
class Turn:
    """One completed exchange. The unit of the recent window."""

    player_input: str
    narration: str
    speaker: str = "The party"

    def messages(self) -> tuple[Message, Message]:
        return (
            Message(role=Role.USER, content=f"{self.speaker} says:\n\n{self.player_input}"),
            Message(role=Role.ASSISTANT, content=self.narration),
        )


@dataclass
class CampaignContext:
    """Everything about the campaign that the prompt is rebuilt from each turn."""

    name: str
    premise: str = ""
    scene: str = ""
    party: list[PartyMember] = field(default_factory=list)
    ledger: CanonLedger = field(default_factory=CanonLedger)
    history: list[Turn] = field(default_factory=list)

    def record(self, turn: Turn) -> None:
        self.history.append(turn)

    def window(self, size: int = DEFAULT_WINDOW) -> tuple[Message, ...]:
        """The last `size` turns as alternating messages. Never the full transcript."""
        if size <= 0:
            return ()
        messages: list[Message] = []
        for turn in self.history[-size:]:
            messages.extend(turn.messages())
        return tuple(messages)


class GMPromptBuilder:
    """Builds the `GMRequest` for one turn. Holds no state between calls."""

    def __init__(self, scaffolding: str = "high", window: int = DEFAULT_WINDOW) -> None:
        if scaffolding not in SCAFFOLDING_TEMPLATES:
            raise ValueError(
                f"unknown scaffolding level {scaffolding!r} "
                f"(expected one of: {', '.join(sorted(SCAFFOLDING_TEMPLATES))})"
            )
        self.scaffolding = scaffolding
        self.window = window

    # --- the three parts ---------------------------------------------------

    def system(self) -> str:
        """Session-stable instructions. This is the cached prefix."""
        return render_template(
            "system_core",
            scaffolding_directive=render_template(SCAFFOLDING_TEMPLATES[self.scaffolding]),
        )

    def campaign_state(self, campaign: CampaignContext) -> str:
        """Volatile half: what is true right now."""
        return render_template(
            "context",
            campaign=_campaign_block(campaign),
            party=_party_block(campaign.party),
            scene=campaign.scene.strip() or _NO_SCENE,
            canon=render_entries(campaign.ledger.for_gm()),
        )

    def turn_message(
        self,
        player_input: str,
        speaker: str = "The party",
        resolutions: Sequence[str] = (),
    ) -> Message:
        """This turn's input, with any engine results attached (D-001's handoff)."""
        return Message(
            role=Role.USER,
            content=render_template(
                "turn",
                speaker=speaker,
                player_input=player_input.strip(),
                resolutions=_resolutions_block(resolutions),
            ),
        )

    def resolution_message(self, resolutions: Sequence[str]) -> Message:
        """The follow-up after the engine resolved a check the GM asked for."""
        return Message(
            role=Role.USER,
            content=render_template("resolution", resolutions=_resolutions_block(resolutions)),
        )

    # --- assembly ----------------------------------------------------------

    def build(
        self,
        campaign: CampaignContext,
        player_input: str,
        speaker: str = "The party",
        resolutions: Sequence[str] = (),
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str | None = None,
        call_id: str | None = None,
        interim: str = "",
    ) -> GMRequest:
        """Assemble one call.

        `interim` is the GM's own narration from earlier in *this* turn — the lead-up it
        wrote before asking for a check. Feeding it back as an assistant message is what
        stops the second call from restaging an attempt it has already described; without
        it the player reads the same moment twice.
        """
        turn: list[Message] = [
            self.turn_message(
                player_input,
                speaker=speaker,
                resolutions=() if interim else resolutions,
            )
        ]
        if interim:
            turn.append(Message(role=Role.ASSISTANT, content=interim))
            turn.append(self.resolution_message(resolutions))

        return GMRequest(
            system=self.system(),
            system_volatile=self.campaign_state(campaign),
            messages=(*campaign.window(self.window), *turn),
            model=model,
            max_tokens=max_tokens,
            effort=effort,
            call_id=call_id,
        )


# --- section rendering -----------------------------------------------------


def _campaign_block(campaign: CampaignContext) -> str:
    lines = [f"**{campaign.name}**"]
    if campaign.premise.strip():
        lines.append(campaign.premise.strip())
    return "\n\n".join(lines)


def _party_block(party: Sequence[PartyMember]) -> str:
    if not party:
        return _NO_PARTY
    return "\n".join(member.render() for member in party)


def _resolutions_block(resolutions: Sequence[str]) -> str:
    if not resolutions:
        return _NO_RESOLUTIONS
    header = (
        "These are the engine's results. They are authoritative: narrate them "
        "faithfully and do not change, soften, or extend them. Convey them "
        "qualitatively — never quote a number back (OD-11); the interface shows those:"
    )
    body = "\n".join(f"- {line}" for line in resolutions)
    return f"{header}\n\n{body}"


def entries_for_prompt(ledger: CanonLedger) -> list[CanonEntry]:
    """What the GM seat sees: everything, secrets included (D-003)."""
    return ledger.for_gm()
