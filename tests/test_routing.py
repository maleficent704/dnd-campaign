"""P4.3: choosing which Ollama host serves a seat, and the NPC turn that uses it.

Offline throughout. The probe is injected, so "toto-llm is down and sam-pc has no 70B" is
a two-line fixture rather than an afternoon of unplugging things.
"""

from __future__ import annotations

import pytest

from dndc.config import OllamaSeat
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.logging import SessionLog, read_log
from dndc.models import NPC_SEAT, OllamaRouter, RoutingError, build_npc_backend
from dndc.models.mock import MockBackend
from dndc.game.npcturn import NPCVoice
from dndc.schema.events import CallStatus, EventType
from dndc.schema.npc import NPC, VoiceCard

TOTO = "http://192.168.50.11:11434"
SAM = "http://192.168.50.161:11434"
ENDPOINTS = {"toto-llm": TOTO, "sam-pc": SAM}

BIG = "llama3.3:70b"
SMALL = "llama3.1:8b"


def seat(endpoint: str = TOTO, model: str = BIG) -> OllamaSeat:
    return OllamaSeat(backend="ollama", endpoint=endpoint, model=model)


def router(**held) -> OllamaRouter:
    """A router over a fake world: url -> the models that host has, or None if it is down."""
    def probe(url: str):
        value = held.get(url, ())
        return None if value is None else frozenset(value)

    return OllamaRouter(ENDPOINTS, probe=probe)


# --- picking an endpoint ---------------------------------------------------


def test_the_seats_own_endpoint_wins_when_it_has_the_model():
    route = router(**{TOTO: [BIG], SAM: [BIG]}).resolve(seat())
    assert route.endpoint.name == "toto-llm"
    assert route.fell_back is False
    assert route.reason == ""


def test_a_route_is_named_from_the_registry():
    """A log saying "sam-pc" is worth more than one saying a bare IP, and the registry is
    the only place those names exist."""
    assert router(**{TOTO: [BIG]}).resolve(seat()).endpoint.name == "toto-llm"


def test_it_falls_back_when_the_primary_is_unreachable():
    route = router(**{TOTO: None, SAM: [BIG]}).resolve(seat())
    assert route.endpoint.url == SAM
    assert route.fell_back is True
    assert "unreachable" in route.reason


def test_an_endpoint_that_is_up_without_the_model_is_not_a_candidate():
    """The failure this layer exists to prevent: sam-pc answers long before it has a 70B
    pulled, and an empty host fails at generate time, halfway into a scene — which is a
    worse place to find out than here."""
    with pytest.raises(RoutingError):
        router(**{TOTO: None, SAM: [SMALL]}).resolve(seat())
    # And it is genuinely the *model* check doing the work, not the liveness one:
    assert router(**{TOTO: None, SAM: [SMALL, BIG]}).resolve(seat()).endpoint.url == SAM


def test_no_endpoint_with_the_model_raises_and_says_what_it_tried():
    with pytest.raises(RoutingError) as caught:
        router(**{TOTO: None, SAM: [SMALL]}).resolve(seat())
    message = str(caught.value)
    assert "unreachable" in message and SMALL in message
    assert "ollama pull" in message


def test_it_never_substitutes_a_different_model():
    """Voicing an NPC with whatever happened to be loaded is the same class of error as
    hardcoding a model name — and it makes every later measurement a lie."""
    with pytest.raises(RoutingError):
        router(**{TOTO: [SMALL], SAM: [SMALL]}).resolve(seat())


def test_an_untagged_model_matches_the_latest_tag():
    route = router(**{TOTO: ["mistral:latest"]}).resolve(seat(model="mistral"))
    assert route.endpoint.url == TOTO


def test_a_down_host_and_an_empty_host_are_different_answers():
    """One might come back; the other needs a person to go and pull something."""
    down = str(pytest.raises(RoutingError, router(**{TOTO: None, SAM: None}).resolve, seat()).value)
    empty = str(pytest.raises(RoutingError, router(**{TOTO: [], SAM: []}).resolve, seat()).value)
    assert "unreachable" in down and "unreachable" not in empty
    assert "no models" in empty


def test_resolution_is_cached_until_forced():
    """An NPC that probes before every line adds a round trip to every line."""
    probes: list[str] = []

    def probe(url: str):
        probes.append(url)
        return frozenset([BIG])

    routed = OllamaRouter(ENDPOINTS, probe=probe)
    routed.resolve(seat())
    routed.resolve(seat())
    assert probes == [TOTO]

    routed.resolve(seat(), force=True)
    assert probes == [TOTO, TOTO]


def test_the_seat_backend_is_built_from_the_chosen_route():
    class Cfg:
        seats = type("S", (), {"npc": seat()})()
        ollama_endpoints = ENDPOINTS

    backend, route = build_npc_backend(Cfg, router(**{TOTO: None, SAM: [BIG]}))
    assert backend.endpoint == SAM
    assert backend.model == BIG
    assert route.fell_back is True


# --- the NPC turn ----------------------------------------------------------


@pytest.fixture
def ledger() -> CanonLedger:
    book = CanonLedger()
    book.add(CanonEntry(id="w1", text="The tide floods the low road.", tags=("harbour",)))
    book.add(CanonEntry(id="g1", text="The harbourmaster is the paymaster.",
                        scope=CanonScope.GM_ONLY, tags=("harbour",)))
    return book


def maren() -> NPC:
    return NPC.create("Maren", knows_tags=("harbour",), voice=VoiceCard(role="innkeeper"))


def test_a_turn_is_logged_pending_then_complete(ledger, tmp_path):
    log = SessionLog.open(tmp_path)
    voice = NPCVoice(backend=MockBackend(responses=["Aye, twice a month."]), log=log)
    voice.speak(maren(), ledger, "They ask about the low road.")

    turns = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN]
    assert [t.status for t in turns] == [CallStatus.PENDING, CallStatus.COMPLETE]
    assert turns[0].call_id == turns[1].call_id  # OD-9 pairing
    assert turns[1].text == "Aye, twice a month."


def test_the_logged_scope_is_the_permitted_ids(ledger, tmp_path):
    """Ids, not a count: a leak is only measurable against what was in scope (D-008 17)."""
    log = SessionLog.open(tmp_path)
    NPCVoice(backend=MockBackend(responses=["Aye."]), log=log).speak(
        maren(), ledger, "They ask."
    )
    turn = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN][-1]
    assert turn.knowledge_scope == "w1"
    assert "g1" not in (turn.knowledge_scope or "")


def test_the_gatekeeper_verdict_stays_unset_until_there_is_one(ledger, tmp_path):
    """A row saying a check passed when none ran is worse than one that says nothing."""
    log = SessionLog.open(tmp_path)
    NPCVoice(backend=MockBackend(responses=["Aye."]), log=log).speak(maren(), ledger, "?")
    turn = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN][-1]
    assert turn.gatekeeper_verdict is None


def test_a_failed_call_is_logged_as_failed(ledger, tmp_path):
    class Broken(MockBackend):
        def generate(self, request, on_text=None):
            raise RuntimeError("toto-llm went to sleep")

    log = SessionLog.open(tmp_path)
    voice = NPCVoice(backend=Broken(responses=[]), log=log)
    with pytest.raises(RuntimeError):
        voice.speak(maren(), ledger, "They ask.")

    turns = [e for e in read_log(log.path) if e.type is EventType.NPC_TURN]
    assert [t.status for t in turns] == [CallStatus.PENDING, CallStatus.FAILED]


def test_the_cost_row_names_the_npc_seat(ledger, tmp_path):
    log = SessionLog.open(tmp_path)
    NPCVoice(backend=MockBackend(responses=["Aye."]), log=log).speak(maren(), ledger, "?")
    cost = [e for e in read_log(log.path) if e.type is EventType.COST][-1]
    assert cost.seat == NPC_SEAT
    assert cost.billing == "local"


def test_what_she_said_comes_back_in_her_next_prompt(ledger):
    """Kept automatically, because a caller who has to remember eventually will not — and
    a character without a claims ledger mutates her own account inside one conversation."""
    backend = MockBackend(responses=["I've not seen him since Tuesday.", "As I said."])
    voice = NPCVoice(backend=backend)
    npc = maren()
    voice.speak(npc, ledger, "Where is the harbourmaster?")
    voice.speak(npc, ledger, "You're sure?")

    second = backend.calls[-1]
    assert "I've not seen him since Tuesday." in second.system_volatile


def test_forgetting_clears_the_claims_ledger(ledger):
    backend = MockBackend(responses=["Aye.", "Aye again."])
    voice = NPCVoice(backend=backend)
    npc = maren()
    voice.speak(npc, ledger, "?")
    voice.forget(npc)
    voice.speak(npc, ledger, "?")
    assert "Aye." not in backend.calls[-1].system_volatile


def test_the_secret_never_reaches_the_call(ledger):
    """The P4.2 property, asserted again at the layer that actually sends bytes."""
    backend = MockBackend(responses=["Aye."])
    NPCVoice(backend=backend).speak(maren(), ledger, "Who runs the harbour?")
    assert "paymaster" not in backend.calls[-1].full_system
