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

**The gate is optional and the turn does not depend on it** (P4.4). Without one,
`gatekeeper_verdict` stays unset rather than becoming an optimistic `pass` — a row saying a
check passed when none ran is worse than one that says nothing, because the first is
believed. With one, the *displayed* text may differ from the draft, and both are logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from dndc.gm.canon import CanonLedger
from dndc.gm.gatekeeper import Gatekeeper, Judgement, Verdict
from dndc.gm.npcprompt import NPCPromptBuilder, NPCScene
from dndc.logging import SessionLog
from dndc.models import (
    NPC_SEAT,
    GMBackend,
    GMRequest,
    GMResponse,
    Message,
    Role,
    Route,
    new_call_id,
)
from dndc.memory.sweep import LOCAL_BILLING
from dndc.schema.events import CallStatus, Cost, NPCTurn
from dndc.schema.npc import NPC

#: An NPC line is speech, not narration. Short by design — the prompt asks for one to three
#: brief paragraphs, and a ceiling is the backstop for when it does not listen.
DEFAULT_MAX_TOKENS = 400

#: The warm-up asks for one word. What is wanted is the model *load*, not the answer.
WARM_UP_TOKENS = 4


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
    #: The gate's verdict, when there was a gate. `text` is already what to show.
    judgement: Judgement | None = None
    #: What the GM asked this character to address (D-008 item 22), when a director
    #: directed them. Empty when a human drove the call, as `dndc npc speak` does.
    direction: str = ""

    @property
    def draft(self) -> str:
        """What the model said, before any repair."""
        return self.judgement.draft if self.judgement is not None else self.text


@dataclass
class NPCVoice:
    """Runs NPC calls on one seat, logging each and remembering what was said."""

    backend: GMBackend
    log: SessionLog | None = None
    #: Set when the seat was routed, so the log can say which host served the turn and
    #: whether it was the first choice (D-008 item 18).
    route: Route | None = None
    #: The output gate (P4.4). None runs ungated, which is honest and logged as such.
    gate: Gatekeeper | None = None
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
        direction: str = "",
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
        self._emit(npc, "", CallStatus.PENDING, call_id, scope, direction=direction)
        try:
            response = self.backend.generate(request, on_text=on_text)
        except Exception:
            self._emit(npc, "", CallStatus.FAILED, call_id, scope, direction=direction)
            raise

        draft = response.text.strip()
        judgement = self.gate.check(npc, ledger, draft) if self.gate is not None else None
        text = judgement.text if judgement is not None else draft

        self._emit(
            npc, text, CallStatus.COMPLETE, response.call_id, scope, response.model,
            judgement=judgement, direction=direction,
        )
        self._emit_cost(response)
        # The claims ledger remembers what she *said*, not what she drafted. A character
        # held to a line the table never heard would contradict herself out loud to stay
        # consistent with a sentence that was struck before it left her mouth.
        if text:
            self.said.setdefault(npc.id, []).append(text)
        return NPCReply(
            npc=npc,
            text=text,
            response=response,
            scope=scope,
            endpoint=self._endpoint(),
            judgement=judgement,
            direction=direction,
        )

    def warm_up(self) -> int:
        """Pay the cold-load cost before anyone is waiting on it. Returns milliseconds.

        Measured on toto-llm 2026-09-02: a 70B that is not resident costs **~68 s** on its
        first call and ~1-3 s once loaded. Unpaid, that lands on whichever player happens
        to speak to somebody first — a room going quiet mid-scene. Paid here, it lands at
        session start, where nothing is happening yet and a spinner is an honest thing to
        look at.

        The elapsed time is returned rather than swallowed because it is a *finding*: a
        warm-up of 200 ms means the model was already resident and one of a minute means
        it was not, and the 2026-09-02 (e) correction is what happens when that difference
        is inferred instead of measured. It is logged too (`cost.latency_ms`), separately
        from any turn, so a session's first NPC line can never again have a model load
        hidden inside its timing.
        """
        request = GMRequest(
            system="Answer with the single word: ready.",
            messages=(Message(role=Role.USER, content="ready?"),),
            max_tokens=WARM_UP_TOKENS,
            call_id=new_call_id(),
        )
        response = self.backend.generate(request)
        self._emit_cost(response)
        return response.duration_ms or 0

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
        judgement: Judgement | None = None,
        direction: str = "",
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
            direction=direction or None,
            gatekeeper_verdict=judgement.verdict.value if judgement else None,
            gatekeeper_reason=(judgement.reason or None) if judgement else None,
            # Only on divergence (D-008 item 20): a duplicate of every clean line doubles
            # the log to say nothing, and the drafts that matter are the ones that changed.
            draft=(
                judgement.draft
                if judgement is not None and judgement.draft != text
                else None
            ),
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
            latency_ms=response.duration_ms,
        )
