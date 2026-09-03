"""Model seats: the `GMBackend` interface and its adapters (D-004).

`build_gm_backend()` is the only place that turns a billing choice into a concrete
adapter, so the engine never imports one directly and never learns which is in play.
"""

from __future__ import annotations

from dndc.config import Billing, Config
from dndc.models.api import APIBackend
from dndc.models.base import (
    DEFAULT_MAX_TOKENS,
    GMBackend,
    GMBackendError,
    GMRequest,
    GMResponse,
    Message,
    Role,
    Usage,
    new_call_id,
    to_messages,
)
from dndc.models.mock import MockBackend
from dndc.models.ollama import OllamaBackend
from dndc.models.pricing import ModelPrice, estimate_cost, load_prices, price_for
from dndc.models.routing import Endpoint, OllamaRouter, Route, RoutingError
from dndc.models.subscription import THROTTLE_WARNING, SubscriptionBackend

__all__ = [
    "APIBackend",
    "BATCH_SEAT",
    "Endpoint",
    "Billing",
    "DEFAULT_MAX_TOKENS",
    "GM_SEAT",
    "INTERACTIVE_SEAT",
    "NPC_SEAT",
    "GMBackend",
    "GMBackendError",
    "GMRequest",
    "GMResponse",
    "THROTTLE_WARNING",
    "Message",
    "MockBackend",
    "ModelPrice",
    "OllamaBackend",
    "OllamaRouter",
    "Role",
    "Route",
    "RoutingError",
    "SubscriptionBackend",
    "Usage",
    "build_batch_backend",
    "build_gm_backend",
    "build_interactive_backend",
    "build_npc_backend",
    "estimate_cost",
    "load_prices",
    "new_call_id",
    "price_for",
    "to_messages",
]


def build_gm_backend(
    config: Config,
    billing: Billing | None = None,
    threshold: bool = False,
) -> GMBackend:
    """Resolve the GM seat for this session.

    `threshold` selects the Opus escalation model for an authored threshold moment
    (D-004 / OD-3); everything else runs on the Sonnet-class default.
    """
    choice = billing or config.billing.default
    seat = config.seats.gm
    model = seat.model_threshold if threshold else seat.model_default

    if choice is Billing.API:
        return APIBackend(model=model)
    if choice is Billing.SUBSCRIPTION:
        return SubscriptionBackend(model=model)
    raise GMBackendError(f"unknown billing mode: {choice}")


def build_npc_backend(
    config: Config, router: OllamaRouter | None = None
) -> tuple[OllamaBackend, Route | None]:
    """NPC voices — local 70B, routed (D-003, P4.3).

    Without a `router` this is what it has always been: the seat's own endpoint, taken on
    faith. That keeps every existing caller offline and unprobed. Pass a router and the
    endpoint is *chosen* — checked for the model, with the second registered host as the
    fallback — which is what the CLI does for anything that will actually talk.

    The returned `Route` says which host won and whether it was the first choice; the
    caller logs it, because a silent fallback is the one failure this layer can hide.
    """
    seat = config.seats.npc
    if router is None:
        return OllamaBackend(model=seat.model, endpoint=seat.endpoint), None
    route = router.resolve(seat)
    return OllamaBackend(model=route.model, endpoint=route.endpoint.url), route


#: Names for the seats that appear in `cost.seat` and `session_meta.seats`, so a log says
#: which of them ran. Constants rather than literals because the split is only measurable
#: if both halves of the codebase spell it the same way.
GM_SEAT = "gm"
NPC_SEAT = "npc"
INTERACTIVE_SEAT = "utility_interactive"
BATCH_SEAT = "utility_batch"


def build_interactive_backend(
    config: Config, temperature: float | None = None, seed: int | None = None
) -> OllamaBackend:
    """The utility seat the table waits on — the P2.3 sweep, and anything after it.

    Small and fast on purpose (Fable, 2026-08-14): the sweep is confirmation-gated, so a
    model that over-proposes costs a keystroke, while one that takes three minutes costs
    the evening.

    `temperature` is for the caller to set when the job is extraction rather than prose;
    the model and endpoint still come from config, as everything must (OD-5).
    """
    return _ollama(config.seats.utility_interactive, temperature, seed)


def build_batch_backend(
    config: Config, temperature: float | None = None, seed: int | None = None
) -> OllamaBackend:
    """The utility seat nobody waits on — the P2.5 chronicle, its fold, later compression.

    Bigger and slower on purpose. This output is *not* confirmation-gated and goes into
    every later prompt, and the failure it has to avoid — a summary that gets the facts
    right and their relationship wrong — is one no grounding check can catch. The fix is
    a better writer, not a better guard.
    """
    return _ollama(config.seats.utility_batch, temperature, seed)


def _ollama(seat, temperature: float | None, seed: int | None = None) -> OllamaBackend:
    return OllamaBackend(
        model=seat.model, endpoint=seat.endpoint, temperature=temperature, seed=seed
    )
