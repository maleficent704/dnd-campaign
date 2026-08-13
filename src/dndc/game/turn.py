"""The turn loop (P1.3) — where D-001's boundary is actually enforced.

One turn:

    player input
      → GM call        (narrate, or ask for a resolution)
      → if it asked:   engine resolves it, and the GM narrates the outcome
      → events logged  (player_input, gm_adjudication, rules_resolution, gm_narration, cost)

The "intent pre-check" in TASKS.md is the GM's own judgment, expressed as a
`[[CHECK: ...]]` request: it decides whether an action needs a resolution, and the engine
decides what the resolution *is*. That split is D-001's boundary rule verbatim — GM sets
the DC (logged as an adjudication, so Phase 7 can audit whether its rulings were fair),
engine rolls the dice.

Two things this module is careful about:

**The GM is never handed a number** (OD-11). It receives a severity band computed from
the roll; the numbers go to the interface, which renders them from state. A model cannot
restate a value it was never given, which makes the ban structural rather than a matter
of the model following an instruction every single turn.

**Model calls are logged before they are made** (D-008 / OD-9). A `pending` narration
event is written first and a terminal one after, sharing a `call_id`, so a crash
mid-call leaves a reconstructable log rather than a silent gap.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from dndc.gm.canon import CanonEntry
from dndc.gm.canontag import find_canon_tags, strip_canon_tags
from dndc.gm.checkrequest import CheckRequest, CheckRequestError, find_check_request, strip_check_requests
from dndc.gm.inventorytag import InventoryTag, find_inventory_tags, strip_inventory_tags
from dndc.gm.context import CampaignContext, GMPromptBuilder, Turn
from dndc.logging import SessionLog
from dndc.memory.canon_store import CanonStore
from dndc.models.base import GMBackend, GMResponse, new_call_id
from dndc.models.pricing import estimate_cost
from dndc.rules.checks import CheckResult, resolve_check, resolve_save
from dndc.rules.severity import describe_check
from dndc.schema.events import (
    CallStatus,
    Cost,
    DiceRoll,
    GMAdjudication,
    GMNarration,
    PlayerInput,
    RulesResolution,
)
from dndc.schema.sheet import CharacterSheet, Proficiency

def _clean(text: str) -> str:
    """Narration with every machine tag removed, for the screen and the recent window.

    Every stripper, always. A tag left in the window comes back to the GM as its own past
    voice, and it learns to narrate in tags.
    """
    return strip_inventory_tags(strip_canon_tags(strip_check_requests(text)))


#: Max GM calls per turn: one to consider the action, one to narrate the outcome. A
#: second check request is ignored rather than looped on — a turn that keeps asking for
#: rolls is a prompt bug, and an unbounded loop would spend real money discovering it.
MAX_GM_CALLS = 2


@dataclass
class MechanicalResult:
    """What the interface renders. The numbers live here and only here (OD-11)."""

    label: str
    total: int
    dc: int
    success: bool
    faces: tuple[int, ...]
    modifier: int
    seed: int
    actor: str

    def render(self) -> str:
        """ASCII only, deliberately. This is the authoritative numeric display (OD-11),
        and a Windows console that cannot encode an arrow must not take the line with
        it — the numbers are the one thing that has to survive."""
        verdict = "success" if self.success else "failure"
        dice = " + ".join(str(face) for face in self.faces)
        sign = "+" if self.modifier >= 0 else "-"
        return (
            f"{self.actor} - {self.label} check: "
            f"{dice} {sign} {abs(self.modifier)} = {self.total} vs DC {self.dc} -> {verdict}"
        )


@dataclass
class TurnResult:
    """One completed turn, with the narration and the numbers kept separate."""

    narration: str
    player: str
    character: str | None = None
    mechanics: list[MechanicalResult] = field(default_factory=list)
    adjudication: CheckRequest | None = None
    responses: list[GMResponse] = field(default_factory=list)
    refused: bool = False
    #: Facts this turn added to the ledger. Restatements of known canon are not here —
    #: they were suppressed at the store, having established nothing.
    canon: list[CanonEntry] = field(default_factory=list)
    #: Item changes the GM *proposed* this turn. Nothing has been applied and nothing has
    #: been logged: items are state, so a change needs the table's confirmation, and
    #: confirmation is an interface act rather than an engine one (D-008 amended
    #: 2026-08-13; the 2026-08-05 ruling this implements).
    inventory: list[InventoryTag] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(r.reported_usd or 0.0 for r in self.responses)


class TurnEngine:
    """Runs turns against a GM seat. Holds the campaign; the builder holds no state."""

    def __init__(
        self,
        backend: GMBackend,
        campaign: CampaignContext,
        builder: GMPromptBuilder | None = None,
        rng: random.Random | None = None,
        log: SessionLog | None = None,
        max_tokens: int = 1024,
        billing: str = "api",
        prices: dict | None = None,
        canon: CanonStore | None = None,
    ) -> None:
        self.backend = backend
        self.campaign = campaign
        self.builder = builder or GMPromptBuilder()
        self.rng = rng or random.Random()
        self.log = log
        self.max_tokens = max_tokens
        self.billing = billing
        self.prices = prices or {}
        self.canon = canon if canon is not None else CanonStore(campaign.ledger, log=log)
        # The store and the prompt must read the *same* ledger object, or a fact
        # established this turn is filed to disk and still missing from next turn's
        # prompt — the exact silent failure D-002 exists to prevent. Rebinding here makes
        # that impossible to get wrong from the outside rather than merely documented.
        self.campaign.ledger = self.canon.ledger

    # --- the loop ----------------------------------------------------------

    def open_scene(self, on_text: Callable[[str], None] | None = None) -> TurnResult:
        """The GM's opening narration, before anyone has typed anything.

        At a table the GM speaks first; the loop used to sit waiting for a player who had
        not been told where they were standing (found in the first playtest). No
        `player_input` event is emitted because no player spoke, and a check request is
        stripped rather than resolved — nothing has been attempted yet.
        """
        response, established, items = self._call(
            "", speaker="", resolutions=(), interim="", on_text=on_text, opening=True
        )
        narration = _clean(response.text)
        self.campaign.record(
            Turn(player_input="", narration=narration, speaker="", opening=True)
        )
        return TurnResult(
            narration=narration,
            player="",
            responses=[response],
            refused=response.refused,
            canon=established,
            inventory=items,
        )

    def run(
        self,
        player_input: str,
        player: str,
        sheet: CharacterSheet | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> TurnResult:
        character = sheet.name if sheet is not None else None
        speaker = f"{player} ({character})" if character else player
        self._emit(PlayerInput, player=player, character=character, text=player_input)

        result = TurnResult(narration="", player=player, character=character)
        resolutions: tuple[str, ...] = ()
        interim = ""
        narrations: list[str] = []

        for call_index in range(MAX_GM_CALLS):
            response, established, items = self._call(
                player_input, speaker, resolutions, interim=interim, on_text=on_text
            )
            result.responses.append(response)
            result.canon.extend(established)
            result.inventory.extend(items)

            if response.refused:
                result.refused = True
                result.narration = response.text
                break

            narration = _clean(response.text)
            if narration:
                narrations.append(narration)
            result.narration = "\n\n".join(narrations)

            request = self._check_request(response.text)
            last_call = call_index == MAX_GM_CALLS - 1
            if request is None or last_call:
                break

            # The GM asked for a resolution. Rule, roll, and go round once more, handing
            # back its own lead-up so it continues the scene instead of restaging it.
            result.adjudication = request
            mechanical, description = self._resolve(request, sheet, character or player)
            result.mechanics.append(mechanical)
            resolutions = (description,)
            interim = narration

        self.campaign.record(
            Turn(player_input=player_input, narration=result.narration, speaker=speaker)
        )
        return result

    # --- pieces ------------------------------------------------------------

    def _call(
        self,
        player_input: str,
        speaker: str,
        resolutions: tuple[str, ...],
        interim: str,
        on_text: Callable[[str], None] | None,
        opening: bool = False,
    ) -> tuple[GMResponse, list[CanonEntry], list[InventoryTag]]:
        # The id is minted *here*, not in the backend, because the pending write happens
        # before the response exists — an id created alongside the response could never
        # be on the row that precedes it, which is exactly the pairing OD-9 asked for.
        call_id = new_call_id()
        request = self.builder.build(
            self.campaign,
            player_input=player_input,
            speaker=speaker,
            resolutions=resolutions,
            max_tokens=self.max_tokens,
            call_id=call_id,
            interim=interim,
            opening=opening,
        )

        # Intent before the external call (D-008): a crash here leaves a pending row,
        # not a hole.
        self._emit(GMNarration, text="", status=CallStatus.PENDING, call_id=call_id)

        try:
            response = self.backend.generate(request, on_text=on_text)
        except Exception:
            # The terminal write the pending row was promised. Without it a crashed call
            # is indistinguishable from one still in flight.
            self._emit(GMNarration, text="", status=CallStatus.FAILED, call_id=call_id)
            raise

        self._emit(
            GMNarration,
            text=response.text,
            model=response.model,
            status=CallStatus.COMPLETE,
            call_id=response.call_id,
            scaffolding=self.builder.scaffolding,
        )
        self._emit_cost(response)
        # Extraction happens here rather than in `run`/`open_scene` because this is the
        # one place every GM call passes through. A second narration call in the same turn
        # can establish facts too, and a code path that forgot to look would lose them
        # silently — the failure mode that is hardest to notice and worst to inherit.
        # Canon is filed on the spot; item changes are only *collected*, because the
        # sheet does not move until the table says so.
        return response, self._record_canon(response), self._item_proposals(response)

    def _record_canon(self, response: GMResponse) -> list[CanonEntry]:
        """File whatever the GM declared. A refusal declares nothing."""
        if response.refused or not response.text:
            return []
        return self.canon.record_tags(
            find_canon_tags(response.text),
            session=self.log.session_id if self.log is not None else None,
            # The turn this fact was established on. `history` is appended after the turn
            # completes, so the turn in progress is the next one.
            turn=len(self.campaign.history) + 1,
        )

    def _item_proposals(self, response: GMResponse) -> list[InventoryTag]:
        """What the GM said the party picked up or lost. A refusal proposes nothing."""
        if response.refused or not response.text:
            return []
        return find_inventory_tags(response.text)

    def _check_request(self, text: str) -> CheckRequest | None:
        """A malformed request is a narration, not a crash — the turn still lands."""
        try:
            return find_check_request(text)
        except CheckRequestError:
            return None

    def _resolve(
        self,
        request: CheckRequest,
        sheet: CharacterSheet | None,
        actor: str,
    ) -> tuple[MechanicalResult, str]:
        """Engine computes; GM gets severity only (OD-11)."""
        seed = self.rng.randrange(2**32)
        rng = random.Random(seed)

        ability_score = 10
        level = 1
        proficiency = Proficiency.NONE
        proficient_save = False
        if sheet is not None:
            level = sheet.level
            ability_score = sheet.abilities.score(request.ability)
            if request.skill is not None:
                proficiency = sheet.proficiencies.skills.get(request.skill, Proficiency.NONE)
            proficient_save = request.ability in sheet.proficiencies.saving_throws

        if request.is_save:
            outcome = resolve_save(
                rng,
                ability_score=ability_score,
                dc=request.dc,
                level=level,
                proficient=proficient_save,
                ability=request.ability.value,
            )
        else:
            outcome = resolve_check(
                rng,
                ability_score=ability_score,
                dc=request.dc,
                level=level,
                proficiency=proficiency,
                ability=request.ability.value,
                skill=request.skill.value if request.skill else None,
            )

        # Resolution first, then the ruling that governed it. The ruling logically comes
        # first, but the log is append-only and D-008 wants `resolution_seq` *on* the
        # adjudication — writing it after is what lets that link be exact instead of a
        # second patch-up row. Nothing external happens between the two, so there is no
        # crash window to protect (unlike a model call, which does log intent first).
        resolution_seq = self._emit_resolution(outcome, request, actor, seed)
        self._emit(
            GMAdjudication,
            situation=request.raw,
            ruling=f"{request.label} DC {request.dc}",
            dc=request.dc,
            ability=request.ability.value,
            rationale=request.stakes or None,
            resolution_seq=resolution_seq,
        )

        mechanical = MechanicalResult(
            label=request.label,
            total=outcome.roll.total,
            dc=request.dc,
            success=outcome.success,
            faces=tuple(outcome.roll.rolls),
            modifier=outcome.roll.modifier,
            seed=seed,
            actor=actor,
        )
        return mechanical, describe_check(outcome, actor)

    # --- logging -----------------------------------------------------------

    def _emit(self, event_type, **fields) -> int | None:
        if self.log is None:
            return None
        return self.log.emit(event_type, **fields).seq

    def _emit_resolution(
        self, outcome: CheckResult, request: CheckRequest, actor: str, seed: int
    ) -> int | None:
        return self._emit(
            RulesResolution,
            kind=outcome.kind,
            actor=actor,
            ability=outcome.ability,
            skill=outcome.skill,
            dc=request.dc,
            roll=DiceRoll(
                expression="1d20",
                rolls=tuple(outcome.roll.rolls),
                # `rolls` holds both dice under advantage; `natural` is the one kept.
                kept=(outcome.roll.natural,),
                modifier=outcome.roll.modifier,
                total=outcome.roll.total,
            ),
            advantage=outcome.roll.advantage.value,
            success=outcome.success,
            seed=seed,
        )

    def _emit_cost(self, response: GMResponse) -> None:
        if self.log is None:
            return
        usage = response.usage
        estimated = estimate_cost(usage, response.model, self.prices) if self.prices else None
        subscription = self.billing == "subscription"
        self.log.emit(
            Cost,
            seat="gm",
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            # In subscription mode the dollar figure is what the call *would* have cost
            # at API rates — that is what makes the D-004 toggle measurable (OD-10).
            usd=response.reported_usd if response.reported_usd is not None else estimated,
            would_have_cost=subscription,
            call_id=response.call_id,
        )
