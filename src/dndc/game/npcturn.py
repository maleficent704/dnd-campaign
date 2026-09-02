"""Running one NPC's turn (P4.3, D-003).

Thin on purpose. The interesting decisions are elsewhere — what an NPC may know is
`CanonLedger.for_npc`, what its prompt says is `gm/npcprompt.py`, and which host answers is
`models/routing.py`. This module calls them in the right order, writes the log rows, and
keeps the claims ledger.

**The claims ledger is kept here rather than asked for.** Every reply this NPC gives is
remembered and fed back into its next prompt. The mystery's single most load-bearing
finding was that a character without one mutates its own account inside a single
conversation — and an innkeeper who contradicts her last answer is not a character, she is
a random-sentence generator with a name. Making it automatic means a caller cannot forget
it, which is the same reasoning as the prompt builder taking a ledger rather than entries.

**The gatekeeper is not here yet** (P4.4). `npc_turn.gatekeeper_verdict` stays unset rather
than being filled with an optimistic `pass`: a row saying a check passed when no check ran
is worse than a row that says nothing, because the first one is believed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from dndc.gm.canon import CanonLedger
from dndc.gm.npcprompt import NPCPromptBuilder, NPCScene
from dndc.logging import SessionLog
from dndc.models import NPC_SEAT, GMBackend, GMResponse, Route, new_call_id
from dndc.memory.sweep import LOCAL_BILLING
from dndc.schema.events import CallStatus, Cost, NPCTurn
from dndc.schema.npc import NPC

#: An NPC line is speech, not narration. Short by design — the prompt asks for one to three
#: brief paragraphs, and a ceiling is the backstop for when it does not listen.
DEFAULT_MAX_TOKENS = 400


@dataclass(frozen=True)
class NPCReply:
    """What one NPC said, and everything needed to judge it later."""

    npc: NPC
    text: str
    response: GMResponse
    #: The canon entry ids this character was permitted at the moment of the call — the
    #: denominator for every leak question Phase 7 will ask (D-008 item 17).
    scope: tuple[str, ...] = ()
    #: Which Ollama host answered.
    endpoint: str = ""


@dataclass
class NPCVoice:
    """Runs NPC calls on one seat, logging each and remembering what was said."""

    backend: GMBackend
    log: SessionLog | None = None
    #: Set when the seat was routed, so the log can say which host served the turn and
    #: whether it was the first choice (D-008 item 18).
    route: Route | None = None
    builder: NPCPromptBuilder = field(default_factory=NPCPromptBuilder)
    max_tokens: int = DEFAULT_MAX_TOKENS
    #: Per-NPC claims ledger, keyed by id: what each character has already said tonight.
    said: dict[str, list[str]] = field(default_factory=dict)

    def speak(
        self,
        npc: NPC,
        ledger: CanonLedger,
        prompt: str,
        setting: str = "",
        on_text: Callable[[str], None] | None = None,
    ) -> NPCReply:
        """One line from one character. `prompt` is the GM describing the moment to them."""
        scope = tuple(entry.id for entry in ledger.for_npc(npc))
        scene = NPCScene(
            setting=setting, said=tuple(self.said.get(npc.id, ())), prompt=prompt
        )

        # Minted before the call so the pending row can carry it (OD-9).
        call_id = new_call_id()
        request = self.builder.build(
            npc, ledger, scene, max_tokens=self.max_tokens, call_id=call_id
        )
        self._emit(npc, "", CallStatus.PENDING, call_id, scope)
        try:
            response = self.backend.generate(request, on_text=on_text)
        except Exception:
            self._emit(npc, "", CallStatus.FAILED, call_id, scope)
            raise

        text = response.text.strip()
        self._emit(npc, text, CallStatus.COMPLETE, response.call_id, scope, response.model)
        self._emit_cost(response)
        if text:
            self.said.setdefault(npc.id, []).append(text)
        return NPCReply(
            npc=npc, text=text, response=response, scope=scope, endpoint=self._endpoint()
        )

    def forget(self, npc: NPC) -> None:
        """Drop a character's claims ledger — a new scene, days later, with new people."""
        self.said.pop(npc.id, None)

    # --- logging -----------------------------------------------------------

    def _endpoint(self) -> str:
        if self.route is not None:
            return self.route.endpoint.name
        return getattr(self.backend, "endpoint", "")

    def _emit(
        self,
        npc: NPC,
        text: str,
        status: CallStatus,
        call_id: str | None,
        scope: tuple[str, ...],
        model: str | None = None,
    ) -> None:
        if self.log is None:
            return
        self.log.emit(
            NPCTurn,
            npc=npc.name,
            text=text,
            model=model,
            status=status,
            call_id=call_id,
            # Ids rather than a count: a leak is only measurable against what was in scope
            # at the time, and the scope moves as canon is written (D-008 item 17).
            knowledge_scope=",".join(scope),
            endpoint=self._endpoint(),
        )

    def _emit_cost(self, response: GMResponse) -> None:
        if self.log is None:
            return
        usage = response.usage
        self.log.emit(
            Cost,
            seat=NPC_SEAT,
            model=response.model,
            billing=LOCAL_BILLING,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            usd=response.reported_usd,
            call_id=response.call_id,
        )
