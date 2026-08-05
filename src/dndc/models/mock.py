"""Mock GM seat — the reason the test suite needs no network, GPU, or API key.

Records every request it receives so tests can assert on what the prompt builder
actually sent, which is the part of Phase 1 most likely to regress silently.
"""

from __future__ import annotations

import itertools
from typing import Callable, Iterable

from dndc.models.base import (
    GMBackend,
    GMBackendError,
    GMRequest,
    GMResponse,
    Usage,
    new_call_id,
)


class MockBackend(GMBackend):
    """Replays scripted responses and records the calls that asked for them."""

    name = "mock"

    def __init__(
        self,
        responses: Iterable[str | GMResponse] | None = None,
        model: str = "mock-model",
        usage: Usage | None = None,
        repeat_last: bool = True,
    ) -> None:
        self.model = model
        self.usage = usage or Usage(input_tokens=10, output_tokens=5)
        self.repeat_last = repeat_last
        self.calls: list[GMRequest] = []
        self._scripted = list(responses or ["The tavern door creaks open."])
        self._cursor = itertools.count()

    def generate(
        self,
        request: GMRequest,
        on_text: Callable[[str], None] | None = None,
    ) -> GMResponse:
        self.calls.append(request)
        index = next(self._cursor)

        if index < len(self._scripted):
            scripted = self._scripted[index]
        elif self.repeat_last and self._scripted:
            scripted = self._scripted[-1]
        else:
            raise GMBackendError(
                f"MockBackend ran out of scripted responses at call {index + 1}"
            )

        if isinstance(scripted, GMResponse):
            response = scripted
        else:
            response = GMResponse(
                text=scripted,
                model=request.model or self.model,
                usage=self.usage,
                stop_reason="end_turn",
                call_id=request.call_id or new_call_id(),
            )

        if on_text is not None and response.text:
            on_text(response.text)
        return response

    @property
    def last_request(self) -> GMRequest:
        if not self.calls:
            raise AssertionError("MockBackend has not been called")
        return self.calls[-1]
