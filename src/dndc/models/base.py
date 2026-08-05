"""`GMBackend` — the one seat the GM brain speaks through (D-004).

Two adapters sit behind this interface: `api` (Anthropic SDK, metered against the key
in `.env`) and `subscription` (headless Claude Code under the household Max login).
The engine must not be able to tell them apart — that is the whole point of D-004, and
it is what keeps the turn loop robust to Anthropic changing how billing works again.

Nothing here imports a vendor SDK. Adapters import their own dependencies lazily so the
rules core, the CLI, and the whole test suite keep working with no SDK installed and no
network.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

#: Sensible ceiling for a narration turn. Streaming is used everywhere, so this is a
#: safety rail against a runaway response rather than a latency tradeoff.
DEFAULT_MAX_TOKENS = 8192


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    """Token counts for one call, cache-aware.

    Cache fields matter for more than cost: if `cache_read` stays zero across a session,
    the prompt prefix is being invalidated every turn — which for a GM prompt rebuilt
    from a canon ledger (D-002) is a bug, not a pricing detail.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass(frozen=True)
class GMRequest:
    """One call to the GM seat.

    `system` is kept separate from `messages` because it is the stable cache prefix —
    the canon ledger and world state live here, the turn's input does not.

    The system half is split in two because those halves change on different clocks.
    `system` holds what is fixed for the whole session (the GM's instructions, the
    scaffolding setting) and carries the cache breakpoint. `system_volatile` holds
    campaign state — canon, party HP, the current scene — which changes as play
    proceeds. Keeping them in one string would mean a single hit point of damage
    invalidates the cached copy of the entire instruction set (P1.2).
    """

    system: str
    #: State that changes during a session. Rendered after `system`, outside the cache
    #: breakpoint. Empty for callers that have no state to send.
    system_volatile: str = ""
    messages: tuple[Message, ...] = ()
    max_tokens: int = DEFAULT_MAX_TOKENS
    #: None means "the seat's configured model" — never hardcode one (OD-5).
    model: str | None = None
    #: low | medium | high | xhigh | max. None leaves the model default alone.
    effort: str | None = None
    #: Correlation id for this call (OD-9). Set it when the caller must log `pending`
    #: *before* the call — the id has to exist before the response does, or the two
    #: writes cannot be paired. Backends echo it; None means the backend mints one.
    call_id: str | None = None
    #: Cache the system prefix. On by default; the GM prompt is large and rebuilt every
    #: turn from the same ledger, which is exactly the shape caching pays for.
    cache_system: bool = True

    def with_model(self, model: str) -> GMRequest:
        return GMRequest(
            system=self.system,
            system_volatile=self.system_volatile,
            messages=self.messages,
            max_tokens=self.max_tokens,
            model=model,
            effort=self.effort,
            cache_system=self.cache_system,
            call_id=self.call_id,
        )

    @property
    def full_system(self) -> str:
        """Both halves as one string, for backends without a block-structured API."""
        if not self.system_volatile:
            return self.system
        return f"{self.system}\n\n{self.system_volatile}"


@dataclass(frozen=True)
class GMResponse:
    """What a backend returns. `refused` is checked before `text` is trusted."""

    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None
    #: Shared with the events this call produces (OD-9).
    call_id: str = ""
    #: True when safety classifiers declined the request. Claude Opus 5 and Sonnet 5
    #: return this as a successful HTTP 200 with `stop_reason == "refusal"`, so a
    #: caller that reads `text` without checking gets an empty or partial string.
    refused: bool = False
    refusal_category: str | None = None
    #: Backend-reported dollar cost, when the backend knows it (subscription mode does).
    reported_usd: float | None = None
    #: Wall-clock milliseconds, for the session cost report.
    duration_ms: int | None = None


class GMBackendError(RuntimeError):
    """A backend failed in a way the caller cannot paper over."""


class GMBackend(ABC):
    """The GM seat. One implementation per billing path (D-004)."""

    #: `api` | `subscription` | `ollama` | `mock`
    name: str = "abstract"

    @abstractmethod
    def generate(
        self,
        request: GMRequest,
        on_text: Callable[[str], None] | None = None,
    ) -> GMResponse:
        """Run one turn. `on_text` receives incremental text as it streams."""

    def close(self) -> None:
        """Release any held resources. Safe to call more than once."""


def new_call_id() -> str:
    """Correlates the pending and terminal writes of one model call (OD-9)."""
    return uuid.uuid4().hex


def to_messages(items: Sequence[tuple[str, str]]) -> tuple[Message, ...]:
    """Convenience for building history from (role, text) pairs."""
    return tuple(Message(role=Role(role), content=text) for role, text in items)
