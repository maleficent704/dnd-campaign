"""The combat turn loop (P3.4) — D-001's boundary under its heaviest load.

One turn:

    an actor acts
      → the rules core resolves it        (rules/combat.py, rules/checks.py)
      → the recorder writes it down       (game/combatlog.py, D-008)
      → the GM narrates what it is handed (severity bands, never a number)

The order matters. The fight is fully decided before a model sees any of it, so a
narration cannot change an outcome, and a session that loses its GM mid-fight still has a
complete and correct combat log.

**The GM is handed severity words, not integers** — `rules/severity.py`, relative to the
target's own maximum, because six damage is a scratch to a barbarian and nearly lethal to
a level-1 wizard. This is OD-12 at full strength: the model cannot restate a number it was
never given, and the CLI renders the real ones from state beside the prose.

**Monster tactics are the GM's** (Fable, 2026-08-15 (c)). It declares who a monster goes
for with `[[TARGET: ...]]` in the narration call it already makes, and the engine honours
the declaration. Replay survives because the judgment is *logged* and read back, exactly
as a GM-set DC already is — which is the argument that unblocked this. The deterministic
policy in `choose_target` remains as the fallback, and every fallback is logged as one:
a fight must never stall on a missing tag, and Phase 7 must never have to guess whether a
choice was made or defaulted.

**A multiattack the stat block did not resolve is never quietly one attack.** P3.2 left 41
of 68 unresolved because their sentences offer choices or conditions. Where the sentence
at least states a count, the plan uses that count with the monster's first attack and
**says it approximated**; where it does not, the plan is one attack and says that too.
Silence would be the wrong answer that looks like a right one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Sequence

from dndc.game.combatlog import CombatRecorder
from dndc.game.party import resolve_member
from dndc.gm.context import CampaignContext, GMPromptBuilder
from dndc.gm.targettag import find_target_declarations, strip_target_declarations
from dndc.gm.templates import render_template
from dndc.models import GM_SEAT
from dndc.models.base import GMBackend, GMRequest, GMResponse, Message, Role, new_call_id
from dndc.rules.checks import AttackResult, resolve_attack
from dndc.rules.combat import Combatant, DamageOutcome, Encounter, Side
from dndc.rules.severity import damage_severity
from dndc.rules.statblock import Attack, StatBlock
from dndc.schema.events import CallStatus, Cost, GMNarration, TargetSource

#: A turn with no attack still costs a model call if it narrates, so a turn that did
#: nothing narrates nothing. Silence is cheaper and more honest than "the wolf hesitates".
_NOTHING_HAPPENED = ""


@dataclass(frozen=True)
class PlannedAttack:
    """One swing the engine intends to make."""

    attack: Attack
    target_id: str


@dataclass
class AttackPlan:
    """What an actor is about to do, and how sure the engine is about it."""

    attacks: list[PlannedAttack] = field(default_factory=list)
    #: True when a multiattack sentence could not be resolved and this is the engine's
    #: best reading of it. Never silent — the caller shows it.
    approximated: bool = False
    #: The stat block's own words, when they could not be turned into a plan.
    note: str = ""
    #: Who chose the target. `None` on a plan the caller assembled itself — a player's.
    target_source: TargetSource | None = None


@dataclass
class TurnOutcome:
    """One combatant's turn: what was rolled, what it did, and what the GM said."""

    actor: str
    narration: str = ""
    attacks: list[AttackResult] = field(default_factory=list)
    damage: list[DamageOutcome] = field(default_factory=list)
    #: Severity words handed to the GM. Kept so a test can assert no number reached it.
    severities: list[str] = field(default_factory=list)
    approximated: bool = False
    note: str = ""
    #: Who this turn attacked, and who decided (D-008, amended 2026-08-15 for P3.7).
    target: str | None = None
    target_source: TargetSource | None = None
    responses: list[GMResponse] = field(default_factory=list)
    refused: bool = False

    @property
    def acted(self) -> bool:
        return bool(self.attacks)


def choose_target(encounter: Encounter, actor: Combatant) -> Combatant | None:
    """Which enemy an engine-run combatant swings at.

    Deterministic and deliberately dull: the *most wounded* standing enemy, ties broken by
    initiative order. A model choosing here would make the fight unreplayable, and a
    random choice would make it unreproducible without threading another generator
    through. "Focus the hurt one" is also roughly what a pack does, so the dull rule is
    not an obviously wrong one.
    """
    standing = [
        encounter.combatants[cid]
        for cid in encounter.order
        if encounter.combatants[cid].side is not actor.side
        and not encounter.combatants[cid].down
    ]
    if not standing:
        return None
    return min(standing, key=lambda c: (c.current_hp, encounter.order.index(c.id)))


def plan_attacks(block: StatBlock, target_id: str) -> AttackPlan:
    """Turn a stat block's actions into the swings for one turn.

    See the module docstring for why an unresolved multiattack is never silently one
    attack. The count in "makes three melee attacks" is a fact even when *which* attacks
    is not, and using it with the monster's first action is far closer than dropping two
    of them on the floor.
    """
    if not block.attacks:
        return AttackPlan(note="no usable attack in this stat block")

    multi = block.multiattack
    if multi is None:
        return AttackPlan(attacks=[PlannedAttack(block.attacks[0], target_id)])

    if multi.resolved:
        planned = []
        for name, times in multi.parts:
            attack = block.attack(name)
            if attack is not None:
                planned.extend(PlannedAttack(attack, target_id) for _ in range(times))
        if planned:
            return AttackPlan(attacks=planned)

    times = max(1, multi.count)
    return AttackPlan(
        attacks=[PlannedAttack(block.attacks[0], target_id) for _ in range(times)],
        approximated=True,
        note=multi.raw,
    )


class CombatEngine:
    """Runs turns of a fight. Owns nothing about the fight itself — that is `Encounter`."""

    def __init__(
        self,
        encounter: Encounter,
        backend: GMBackend | None = None,
        recorder: CombatRecorder | None = None,
        blocks: dict[str, StatBlock] | None = None,
        rng: random.Random | None = None,
        campaign: CampaignContext | None = None,
        builder: GMPromptBuilder | None = None,
        max_tokens: int = 400,
        billing: str = "api",
        prices: dict | None = None,
    ) -> None:
        self.encounter = encounter
        self.backend = backend
        self.recorder = recorder or CombatRecorder("combat")
        self.blocks = blocks or {}
        self.rng = rng or random.Random()
        self.campaign = campaign or CampaignContext(name="combat")
        self.builder = builder or GMPromptBuilder()
        self.max_tokens = max_tokens
        self.billing = billing
        self.prices = prices or {}
        #: Declarations the GM has made for turns that have not happened yet, keyed by
        #: combatant id. Consumed when the turn arrives — a declaration is for one turn,
        #: not a standing order, because a standing order would go stale silently.
        self.declared: dict[str, str] = {}

    # --- turns --------------------------------------------------------------

    def take_turn(
        self, plan: AttackPlan | None = None, on_text: Callable[[str], None] | None = None
    ) -> TurnOutcome:
        """Resolve the active combatant's turn, log it, and have the GM narrate it."""
        actor = self.encounter.active
        outcome = TurnOutcome(actor=actor.id)

        if plan is None:
            plan = self._plan_for(actor)
        outcome.approximated = plan.approximated
        outcome.note = plan.note
        outcome.target_source = plan.target_source
        if plan.attacks:
            outcome.target = plan.attacks[0].target_id

        for planned in plan.attacks:
            target = self.encounter.get(planned.target_id)
            if target.down:
                # The engine does not swing at a corpse to use up a multiattack.
                break
            self._swing(actor, target, planned.attack, outcome)

        self.recorder.turn(
            self.encounter, target=outcome.target, source=outcome.target_source
        )
        if outcome.acted and self.backend is not None:
            self._narrate(actor, outcome, on_text)
        return outcome

    def death_save(self) -> TurnOutcome:
        """A dying combatant's turn. The save is the turn."""
        actor = self.encounter.active
        self.recorder.turn(self.encounter)
        result = self.encounter.death_save(actor.id, self.rng)
        self.recorder.death_save(self.encounter.get(actor.id), result)
        # Said out loud, in words rather than a tally. A death save that happens silently
        # takes the clock out of the tensest part of the game, which was the whole reason
        # a dying combatant still gets a turn.
        outcome = TurnOutcome(actor=actor.id)
        if result.revived:
            said = f"{actor.name} comes back round, barely conscious"
        elif result.died:
            said = f"{actor.name} stops breathing"
        elif result.stabilised:
            said = f"{actor.name} stops slipping — still down, no longer dying"
        elif result.success:
            said = f"{actor.name} holds on"
        else:
            said = f"{actor.name} slips further"
        outcome.severities.append(said)
        return outcome

    def advance(self) -> Combatant:
        return self.encounter.advance()

    # --- pieces -------------------------------------------------------------

    def _plan_for(self, actor: Combatant) -> AttackPlan:
        block = self.blocks.get(actor.id)
        target, source = self.resolve_target(actor)
        if block is None or target is None:
            return AttackPlan(note="" if target else "no standing enemy")
        plan = plan_attacks(block, target.id)
        plan.target_source = source
        return plan

    def resolve_target(self, actor: Combatant) -> tuple[Combatant | None, TargetSource]:
        """Who this combatant attacks, and who decided.

        The GM's declaration wins when it still makes sense. It may not: declarations are
        written a turn ahead, so the named target can be down or gone by the time the turn
        arrives, and that is reported as `stale` rather than quietly replaced — "the GM
        chose badly" and "the GM's choice expired" are different findings.
        """
        declared = self.declared.pop(actor.id, None)
        if declared:
            candidates = [
                c for c in self.encounter.combatants.values()
                if c.side is not actor.side and not c.down
            ]
            matches = resolve_member(declared, candidates)
            if len(matches) == 1:
                return matches[0], TargetSource.DECLARED
            return choose_target(self.encounter, actor), TargetSource.STALE
        return choose_target(self.encounter, actor), TargetSource.POLICY

    def record_declarations(self, text: str) -> int:
        """Take the GM's `[[TARGET: ...]]` tags out of a reply and hold them.

        Matched against the combatants actually in the fight, so a tag naming somebody who
        is not here is dropped now rather than becoming a stale declaration later.
        """
        kept = 0
        for declaration in find_target_declarations(text):
            actors = resolve_member(declaration.actor, list(self.encounter.combatants.values()))
            if len(actors) != 1:
                continue
            self.declared[actors[0].id] = declaration.target
            kept += 1
        return kept

    def _swing(
        self, actor: Combatant, target: Combatant, attack: Attack, outcome: TurnOutcome
    ) -> None:
        seed = self.rng.randrange(2**32)
        rng = random.Random(seed)
        result = resolve_attack(
            rng,
            attack_modifier=attack.attack_bonus,
            target_ac=target.armor_class,
            damage_expression=attack.damage_expression,
        )
        outcome.attacks.append(result)
        resolution_seq = self.recorder.attack(actor, target, result, seed=seed)

        if not result.hit:
            outcome.severities.append(f"{actor.name} misses {target.name}")
            return

        before = target
        damage = self.encounter.damage(target.id, result.damage, attack.damage_type)
        outcome.damage.append(damage)
        self.recorder.hit_points(before, damage, resolution_seq=resolution_seq)
        # The one place a number could leak to the model, and the one place it is
        # converted (OD-12). `damage_severity` reads the target's own maximum, because
        # six damage is a scratch to one character and nearly lethal to another.
        outcome.severities.append(
            f"{actor.name} hits {target.name} with {attack.name} — "
            f"{target.name} is {_felt(damage, target)}"
        )

    def _narrate(
        self, actor: Combatant, outcome: TurnOutcome, on_text: Callable[[str], None] | None
    ) -> None:
        call_id = new_call_id()
        request = GMRequest(
            system=self.builder.system(),
            system_volatile=self.builder.campaign_state(self.campaign),
            messages=(
                Message(
                    role=Role.USER,
                    content=render_template(
                        "combat", resolutions="\n".join(f"- {s}" for s in outcome.severities)
                    ),
                ),
            ),
            max_tokens=self.max_tokens,
            call_id=call_id,
        )

        self._emit(GMNarration, text="", status=CallStatus.PENDING, call_id=call_id)
        try:
            response = self.backend.generate(request, on_text=on_text)
        except Exception:
            # The fight is already resolved and logged; a failed narration costs prose,
            # not state. The terminal row the pending one was promised still gets written.
            self._emit(GMNarration, text="", status=CallStatus.FAILED, call_id=call_id)
            raise

        outcome.responses.append(response)
        outcome.refused = response.refused
        # Declarations are lifted before the text is cleaned for the screen: the tag is
        # machine instruction, and a player should never see the GM planning out loud.
        if not response.refused:
            self.record_declarations(response.text)
        outcome.narration = (
            "" if response.refused else strip_target_declarations(response.text).strip()
        )
        self._emit(
            GMNarration,
            text=response.text,
            model=response.model,
            status=CallStatus.COMPLETE,
            call_id=response.call_id,
            scene="combat",
        )
        self._emit_cost(response)

    # --- logging ------------------------------------------------------------

    def _emit(self, event_type, **fields):
        log = self.recorder.log
        return log.emit(event_type, **fields) if log is not None else None

    def _emit_cost(self, response: GMResponse) -> None:
        log = self.recorder.log
        if log is None:
            return
        from dndc.models.pricing import estimate_cost

        usage = response.usage
        estimated = estimate_cost(usage, response.model, self.prices) if self.prices else None
        log.emit(
            Cost,
            seat=GM_SEAT,
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd if response.reported_usd is not None else estimated,
            would_have_cost=self.billing == "subscription",
            call_id=response.call_id,
        )


def run_round(
    engine: CombatEngine,
    plan_for: Callable[[Combatant], AttackPlan | None] | None = None,
    on_text: Callable[[str], None] | None = None,
) -> list[TurnOutcome]:
    """Every combatant's turn until the order comes round again, or the fight ends.

    A convenience for scripts and tests; the CLI drives `take_turn` itself so a player can
    be asked what they want to do.

    Bounded by the size of the order rather than by the round counter alone. `advance()`
    deliberately stays put when nobody left can act — a defensible thing for it to do and
    an infinite loop for anyone waiting on the round to tick over, which is exactly what
    this function did until a test hung on it.
    """
    outcomes = []
    started = engine.encounter.round
    for _ in range(len(engine.encounter.order)):
        if engine.encounter.round != started or engine.encounter.over:
            break
        actor = engine.encounter.active
        if actor.dying:
            outcomes.append(engine.death_save())
        elif actor.acts:
            plan = plan_for(actor) if plan_for is not None else None
            outcomes.append(engine.take_turn(plan, on_text=on_text))
        engine.advance()
    return outcomes


def _felt(damage: DamageOutcome, target: Combatant) -> str:
    """The severity words for one hit.

    `damage_severity` says "dropped — unconscious and dying" for anything at zero, which
    is right for a character and wrong for a monster: monsters do not make death saves,
    they die. Caught by the first live run, where a wolf on the floor was being described
    to the GM as dying and would have been narrated that way.
    """
    if damage.killed:
        return "killed outright" if damage.massive else "killed"
    return damage_severity(damage.taken, damage.combatant.current_hp, target.max_hp)


__all__ = [
    "AttackPlan",
    "CombatEngine",
    "PlannedAttack",
    "TurnOutcome",
    "choose_target",
    "plan_attacks",
    "run_round",
]
