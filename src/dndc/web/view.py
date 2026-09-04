"""What a player's device may be sent (P6.2).

Every previous phase kept its secrets inside one process, where the only thing that could
leak them was a model. Phase 6 puts a screen in somebody's hands in another room, and the
question changes shape: not "will the GM say this" but "is this in the response". A
browser cannot be trusted, told, or reminded. It can only be sent things or not sent them.

**So the rule is P4.1's, and it is the same rule for the same reason: absent from the
type, not filtered out of it.** There is no `scope` field on anything here, no cast, no
belief register, no prompt, no raw model output. A `gm_only` fact cannot reach a device
through this module because there is nowhere in it for such a fact to sit — which is a
different and much stronger claim than "the code that builds this remembers to exclude
it". `CanonLedger.for_players` is the one door, it is an allow-list, and it is the sibling
of the allow-list the NPC tier has used since P4.1.

**Narration comes from the turn window, never from a model response.** `Turn.narration` has
been through `_clean`, so every `[[...]]` tag is gone — including `[[CANON: gm_only — ...]]`,
which is the single most dangerous string in this system and which sits in plain text in
`GMResponse.text` and in the log. This module never touches either, and the types make
that structural: it is built from `CampaignContext`, which holds turns, and there is no
route from here to a response.

**The view is the table's, not each player's.** Every device sees the same thing, which is
what a hot-seat CLI has always shown and what a physical table has always been — everyone
hears everything. Two devices make per-player secrecy *possible* for the first time, which
is a design question rather than an implementation one, and it is tagged as such in
PROGRESS rather than answered here.
"""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict

from dndc.gm.context import CampaignContext, PartyMember, SpokenLine, Turn

#: What a device is told when nobody has set a scene. Not an empty string: a screen that
#: renders nothing looks broken, and "where are we" is the question a returning table asks
#: first (which is why P5.3 made the recap propose an answer).
NO_SCENE = "(no scene set)"


class _View(BaseModel):
    """Frozen, closed, and serialisable. `extra="forbid"` is load-bearing here rather than
    tidy: it is what makes "there is no field for a secret" enforceable at runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SpokenView(_View):
    """One line an NPC said out loud, post-gate (P4.4).

    Only what was spoken. A character's beliefs, their knowledge scope, and the author's
    notes about them have no representation here — the roster itself is absent from this
    module, so the only way an NPC appears on a device is by having said something in
    front of the party.
    """

    speaker: str
    text: str

    @classmethod
    def of(cls, line: SpokenLine) -> SpokenView:
        return cls(speaker=line.speaker, text=line.text)


class TurnView(_View):
    """One exchange as the table saw it happen."""

    #: "Kelly (Corin Vale)", or empty for the opening scene, which nobody prompted.
    speaker: str
    said: str
    #: Tags already stripped — this is the window's text, not the model's.
    narration: str
    dialogue: tuple[SpokenView, ...] = ()
    opening: bool = False

    @classmethod
    def of(cls, turn: Turn) -> TurnView:
        return cls(
            speaker="" if turn.opening else turn.speaker,
            said="" if turn.opening else turn.player_input,
            narration=turn.narration,
            dialogue=tuple(SpokenView.of(line) for line in turn.dialogue),
            opening=turn.opening,
        )


class MemberView(_View):
    """A character, as their own party sees them.

    Deliberately the same thinness as the GM's party block: names, condition, and how to
    refer to them (P5.5). No sheet, no ledger of what this character privately knows, no
    backstory — a device showing the table's state is not a character sheet viewer, and
    the one that comes later can be asked for explicitly.
    """

    name: str
    player: str
    pronouns: str = ""
    hp_current: int | None = None
    hp_max: int | None = None
    conditions: tuple[str, ...] = ()

    @classmethod
    def of(cls, member: PartyMember) -> MemberView:
        return cls(
            name=member.name,
            player=member.player,
            pronouns=member.pronouns,
            hp_current=member.hp_current,
            hp_max=member.hp_max,
            conditions=tuple(member.conditions),
        )


class TableView(_View):
    """Everything a device is sent about a campaign in progress.

    If a fact is not reachable from here, no browser has it. That is the property this
    type exists to make checkable, and the tests check it on the serialised bytes rather
    than on the object, because the bytes are what actually leaves the machine.
    """

    campaign: str
    scene: str = NO_SCENE
    #: Whose seat it is. Everyone is shown this; only one device may act on it (P6.4).
    acting: str = ""
    party: tuple[MemberView, ...] = ()
    turns: tuple[TurnView, ...] = ()
    #: Canon the party has actually established, and their own characters' facts. Never
    #: `world`, never `npc_belief`, and never `gm_only` — see `CanonLedger.for_players`.
    known: tuple[str, ...] = ()
    #: How many exchanges this campaign has had, which is not `len(turns)` when the window
    #: is trimmed. A device showing "turn 3 of an evening" should not lie about it.
    played: int = 0


def table_view(
    campaign: CampaignContext,
    acting: str = "",
    window: int | None = None,
) -> TableView:
    """The whole of what a device gets, built from campaign state and nothing else.

    `window` trims the transcript to the most recent exchanges. It is a display choice,
    not a secrecy one — nothing becomes safe by being scrolled off — so the default is the
    whole evening, and a caller that wants less asks for less.
    """
    turns: Sequence[Turn] = campaign.history
    if window is not None:
        turns = turns[-window:] if window > 0 else ()

    return TableView(
        campaign=campaign.name,
        scene=campaign.scene or NO_SCENE,
        acting=acting,
        party=tuple(MemberView.of(member) for member in campaign.party),
        turns=tuple(TurnView.of(turn) for turn in turns),
        known=tuple(entry.text for entry in campaign.ledger.for_players()),
        played=len(campaign.history),
    )
