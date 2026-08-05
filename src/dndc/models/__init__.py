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
from dndc.models.subscription import THROTTLE_WARNING, SubscriptionBackend

__all__ = [
    "APIBackend",
    "Billing",
    "DEFAULT_MAX_TOKENS",
    "GMBackend",
    "GMBackendError",
    "GMRequest",
    "GMResponse",
    "THROTTLE_WARNING",
    "Message",
    "MockBackend",
    "ModelPrice",
    "OllamaBackend",
    "Role",
    "SubscriptionBackend",
    "Usage",
    "build_gm_backend",
    "build_npc_backend",
    "build_utility_backend",
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


def build_npc_backend(config: Config) -> OllamaBackend:
    """NPC voices — local 70B on toto-llm (D-003)."""
    seat = config.seats.npc
    return OllamaBackend(model=seat.model, endpoint=seat.endpoint)


def build_utility_backend(config: Config) -> OllamaBackend:
    """Recaps, compression, SRD RAG — the small local seat."""
    seat = config.seats.utility
    return OllamaBackend(model=seat.model, endpoint=seat.endpoint)
