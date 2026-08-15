"""Ollama adapter — NPC voices (Phase 4) and the utility tier (Phase 5).

Registered now so the routing layer has both endpoints from day one (OD-5): toto-llm is
primary, sam-pc is declared but unused until Phase 4. Uses Ollama's native `/api/chat`
over stdlib HTTP — one small JSON POST does not justify a dependency, and the rules core
must stay installable without one.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable

from dndc.models.base import (
    DEFAULT_MAX_TOKENS,
    GMBackend,
    GMBackendError,
    GMRequest,
    GMResponse,
    Usage,
    new_call_id,
)

DEFAULT_TIMEOUT_SECONDS = 300


class OllamaBackend(GMBackend):
    """A local model seat. Free to run, so it is also the all-local test path."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        endpoint: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        opener: Callable[..., object] | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen
        #: None leaves the model's own default alone, which is right for anything that
        #: should sound like a person. Extraction jobs set it low: the P2.3 sweep read one
        #: session twice at the default and answered "23 facts" once and "none" the other
        #: time, which is not a measurement of anything.
        self.temperature = temperature
        #: A tightener, never a guarantee (Fable, 2026-08-15). Ollama honours a seed, but
        #: reproducibility through it is hostage to model version, quantization and
        #: server internals — it breaks silently on the first upgrade, which is exactly
        #: why the drift baseline is a committed fixture and not a seed. Set on analysis
        #: sweeps because narrowing the variance costs nothing; relied on nowhere.
        self.seed = seed

    def payload(self, request: GMRequest) -> dict:
        messages = []
        if request.full_system:
            # One system message: Ollama has no block-level cache control, so the
            # stable/volatile split has nothing to attach to here.
            messages.append({"role": "system", "content": request.full_system})
        messages += [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
        ]
        options: dict[str, object] = {
            "num_predict": request.max_tokens or self.max_tokens
        }
        if self.temperature is not None:
            options["temperature"] = self.temperature
        if self.seed is not None:
            options["seed"] = self.seed
        return {
            "model": request.model or self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

    def generate(
        self,
        request: GMRequest,
        on_text: Callable[[str], None] | None = None,
    ) -> GMResponse:
        body = json.dumps(self.payload(request)).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.endpoint}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.monotonic()
        try:
            with self._open(http_request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise GMBackendError(
                f"could not reach Ollama at {self.endpoint}: {exc}. Endpoints live in "
                f"config.yaml; check the host is up."
            ) from exc
        except json.JSONDecodeError as exc:
            raise GMBackendError(f"Ollama returned invalid JSON: {exc}") from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        text = ((raw.get("message") or {}).get("content")) or ""
        if on_text is not None and text:
            on_text(text)

        return GMResponse(
            text=text,
            model=raw.get("model") or request.model or self.model,
            usage=Usage(
                input_tokens=int(raw.get("prompt_eval_count") or 0),
                output_tokens=int(raw.get("eval_count") or 0),
            ),
            stop_reason=raw.get("done_reason"),
            call_id=request.call_id or new_call_id(),
            #: Local inference is free — an explicit zero, not an unknown.
            reported_usd=0.0,
            duration_ms=duration_ms,
        )
