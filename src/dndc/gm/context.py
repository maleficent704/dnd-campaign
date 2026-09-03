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
from dndc.gm.chronicle import Chronicle
from dndc.gm.templates import render_template
from dndc.models.base import DEFAULT_MAX_TOKENS, GMRequest, Message, Role
from dndc.schema.npc import NPC
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
_NO_CAST = (
    "(nobody in this campaign speaks for themselves yet — voice everyone in your own prose)"
)


@dataclass(frozen=True)
class PartyMember:
    """What the GM needs to know about a character: identity, and current condition.

    Deliberately not the whole sheet. The GM narrates; it does not need proficiency
    bonuses or an inventory manifest to do that, and every token spent here is spent
    every single turn.
    """

    name: str
    player: str
    #: How to refer to them. Blank means the prompt says nothing, and the GM is left to
    #: its own devices — which is the state this field exists to end.
    pronouns: str = ""
    descriptor: str = ""
    hp_current: int | None = None
    hp_max: int | None = None
    conditions: tuple[str, ...] = ()

    @classmethod
    def from_sheet(cls, sheet: CharacterSheet) -> PartyMember:
        return cls(
            name=sheet.name,
            player=sheet.player,
            pronouns=sheet.pronouns,
            descriptor=f"level {sheet.level} {sheet.species} {sheet.character_class}",
            hp_current=sheet.hit_points.current,
            hp_max=sheet.hit_points.maximum,
        )

    def render(self) -> str:
        parts = [f"- **{self.name}** (played by {self.player})"]
        if self.pronouns:
            parts.append(f", {self.pronouns}")
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
class SpokenLine:
    """What one NPC said in their own voice, after the gate (P4.5).

    Kept apart from the narration it followed, and that separation is the point. See
    `_dialogue_block`.
    """

    speaker: str
    text: str


@dataclass(frozen=True)
class Turn:
    """One completed exchange. The unit of the recent window."""

    player_input: str
    narration: str
    speaker: str = "The party"
    #: True for the GM's opening scene, which no player prompted. Kept in the window
    #: because it is what the session is built on, but not attributed to anyone.
    opening: bool = False
    #: Lines spoken by NPCs the GM directed this turn (P4.5). Never part of `narration`:
    #: the GM did not write these and must not read them back as though it had.
    dialogue: tuple[SpokenLine, ...] = ()

    def messages(self, carried: Sequence[SpokenLine] = ()) -> tuple[Message, Message]:
        """This turn as two messages, optionally carrying the *previous* turn's dialogue.

        `carried` is what the NPCs said after the last narration, arriving with this
        turn's player input — the same place engine resolutions arrive, and for the same
        reason: both are things that happened between the GM's turns and neither is the
        GM's own output.
        """
        prompt = (
            "(the session opens)"
            if self.opening
            else f"{self.speaker} says:\n\n{self.player_input}"
        )
        if carried:
            prompt = f"{_dialogue_block(carried)}\n\n{prompt}"
        return (
            Message(role=Role.USER, content=prompt),
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
    #: D-002's third layer (P2.5): earlier sessions as prose. Empty in session one, and
    #: the only reason session nine's prompt does not carry session two's transcript.
    chronicle: Chronicle = field(default_factory=Chronicle)
    history: list[Turn] = field(default_factory=list)
    #: The NPCs this campaign can voice for themselves (P4.5). The GM is shown the roster
    #: so it knows who to direct; it is not shown their knowledge scopes, which are none
    #: of its business — the GM decides *who speaks*, the ledger decides *what they know*.
    cast: list[NPC] = field(default_factory=list)

    def record(self, turn: Turn) -> None:
        self.history.append(turn)

    def window(self, size: int = DEFAULT_WINDOW) -> tuple[Message, ...]:
        """The last `size` turns as alternating messages. Never the full transcript.

        NPC dialogue rides one turn forward: what a character said after turn *n*'s
        narration arrives attached to turn *n+1*'s player input. That keeps the roles
        strictly alternating, and — the reason it is worth the bookkeeping — it keeps
        every NPC line out of the assistant slot. A GM that reads Maren's dialogue back as
        its own past output learns to write Maren's dialogue, and a GM writing Maren's
        lines directly is a GM holding `gm_only` canon speaking with her mouth: exactly
        the leak the whole tier exists to prevent. Protection by construction again.
        """
        if size <= 0:
            return ()
        window = self.history[-size:]
        messages: list[Message] = []
        carried: tuple[SpokenLine, ...] = ()
        for turn in window:
            messages.extend(turn.messages(carried))
            carried = turn.dialogue
        return tuple(messages)

    def pending_dialogue(self) -> tuple[SpokenLine, ...]:
        """What was said after the last narration — it belongs to the turn being built."""
        return self.history[-1].dialogue if self.history else ()


class GMPromptBuilder:
    """Builds the `GMRequest` for one turn. Holds no state between calls."""

    def __init__(self, scaffolding: str = "high", window: int = DEFAULT_WINDOW) -> None:
        self.window = window
        self.set_scaffolding(scaffolding)

    def set_scaffolding(self, scaffolding: str) -> None:
        """Change the D-006 level mid-session (OD-15's `/scaffolding` command).

        Safe to call between turns: `system()` re-renders per call, so the next request
        simply carries a different directive. It does cost one cache miss — the system
        half is the cached prefix and its text has changed — which is the correct price
        for a setting the players are expected to touch once or twice a session.
        """
        if scaffolding not in SCAFFOLDING_TEMPLATES:
            raise ValueError(
                f"unknown scaffolding level {scaffolding!r} "
                f"(expected one of: {', '.join(sorted(SCAFFOLDING_TEMPLATES))})"
            )
        self.scaffolding = scaffolding

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
            chronicle=campaign.chronicle.render(),
            scene=campaign.scene.strip() or _NO_SCENE,
            canon=render_entries(campaign.ledger.for_gm()),
            npcs=_cast_block(campaign.cast),
        )

    def turn_message(
        self,
        player_input: str,
        speaker: str = "The party",
        resolutions: Sequence[str] = (),
        dialogue: Sequence[SpokenLine] = (),
    ) -> Message:
        """This turn's input, with any engine results attached (D-001's handoff).

        `dialogue` is what the NPCs said after the *previous* narration. It arrives here
        rather than in the assistant slot for the reason `window` gives at length.
        """
        content = render_template(
            "turn",
            speaker=speaker,
            player_input=player_input.strip(),
            resolutions=_resolutions_block(resolutions),
        )
        if dialogue:
            content = f"{_dialogue_block(dialogue)}\n\n{content}"
        return Message(role=Role.USER, content=content)

    def opening_message(self) -> Message:
        """The instruction that opens a session, before any player has spoken."""
        return Message(role=Role.USER, content=render_template("opening"))

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
        opening: bool = False,
    ) -> GMRequest:
        """Assemble one call.

        `interim` is the GM's own narration from earlier in *this* turn — the lead-up it
        wrote before asking for a check. Feeding it back as an assistant message is what
        stops the second call from restaging an attempt it has already described; without
        it the player reads the same moment twice.
        """
        turn: list[Message] = [
            self.opening_message()
            if opening
            else self.turn_message(
                player_input,
                speaker=speaker,
                resolutions=() if interim else resolutions,
                # What the NPCs said after the last narration. Dialogue produced *during*
                # this turn reaches the GM on the next one — a character answers at the
                # end of a turn, once the dice have landed, so there is nothing to carry
                # mid-turn except in the rare reply that directs a character and asks for
                # a check in the same breath.
                dialogue=campaign.pending_dialogue(),
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


def _cast_block(cast: Sequence[NPC]) -> str:
    """The roster the GM directs from.

    Role, whereabouts, and the author's notes — the GM is the director and already holds
    `gm_only` canon, so "she is lying about the ledger" is exactly what it needs to direct
    her well. That same field is never rendered into *her own* prompt, and the pair of
    facts is the boundary D-003 draws, stated as sharply as it can be: the character who
    is lying is not told she is lying.

    Knowledge scopes are deliberately absent. The GM chooses who speaks; the ledger
    chooses what they know. A GM shown the scope would start writing directions that
    reach for what is in it.
    """
    if not cast:
        return _NO_CAST
    lines = []
    for npc in cast:
        parts = [f"- **{npc.name}**"]
        if npc.pronouns:
            parts.append(f" ({npc.pronouns})")
        if npc.voice.role:
            parts.append(f" — {npc.voice.role}")
        if npc.location:
            parts.append(f" · {npc.location}")
        if npc.notes:
            parts.append(f"\n  - *(for you alone: {npc.notes})*")
        lines.append("".join(parts))
    return "\n".join(lines)


def _dialogue_block(dialogue: Sequence[SpokenLine]) -> str:
    """NPC lines as they reach the GM: already said, already heard, not yours to redo.

    The framing is doing real work. These lines came from another model with a narrower
    view of the world, and the GM's job now is to continue the scene around them — not to
    improve them, repeat them, or decide they meant something else.
    """
    header = (
        "These characters answered for themselves, out loud, after your last narration. "
        "The table has already heard them. Treat every line as established and spoken — "
        "do not restate it, rewrite it, or contradict it:"
    )
    body = "\n".join(f"- **{line.speaker}:** {line.text}" for line in dialogue)
    return f"{header}\n\n{body}"


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


def render_transcript(turns: Sequence[Turn]) -> str:
    """A run of turns as flat prose, for a utility-tier reader.

    Used by the P2.3 sweep and the P2.5 chronicle, which both read a session back rather
    than continue it — so they want one block of text, not the alternating messages the
    GM prompt is built from.

    Player input is included even though the sweep must not record it. Half the narration
    in a session is a reply — "you push it open, and the hinges give" means nothing
    without the line that prompted it — and a clerk given only the answers writes down
    facts that are missing their subject.
    """
    blocks = []
    for index, turn in enumerate(turns, start=1):
        lines = [f"--- exchange {index} ---"]
        if turn.opening:
            lines.append("(the session opens)")
        elif turn.player_input.strip():
            lines.append(f"{turn.speaker or 'A player'}: {turn.player_input.strip()}")
        lines.append(f"GM: {turn.narration.strip()}")
        # NPC lines are part of what happened, so a reader that skipped them would lose
        # every fact a character established out loud — and dialogue is where most facts
        # about a village get established.
        for spoken in turn.dialogue:
            lines.append(f"{spoken.speaker}: {spoken.text.strip()}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
