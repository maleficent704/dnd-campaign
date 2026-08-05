"""`api` adapter — Anthropic SDK, metered against the key in `.env` (D-004).

Three things this adapter gets right on purpose, because each is a documented way to
break a request on `claude-sonnet-5` / `claude-opus-5`:

* **No sampling parameters.** `temperature`, `top_p`, and `top_k` are rejected with a
  400 on these models. Tone is steered from the prompt template instead (D-006).
* **No `budget_tokens`.** Manual extended thinking is gone; depth is `output_config.effort`.
* **Refusals are not exceptions.** A declined request returns HTTP 200 with
  `stop_reason == "refusal"` and empty or partial content, so `stop_reason` is checked
  before the text is handed to the engine.

Streaming is always used — a narration turn can be long, and streaming is what keeps a
big `max_tokens` from tripping the SDK's HTTP timeout. It also gives the CLI live text.
"""

from __future__ import annotations

import os
import time
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

#: Beta flag for server-side refusal fallbacks. Recommended whenever an Opus-5-class
#: model is in play: a declined request is re-run on the fallback model inside the same
#: call, rather than surfacing an empty turn mid-session.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class APIBackend(GMBackend):
    """GM seat over the Anthropic Messages API."""

    name = "api"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str | None = None,
        use_fallbacks: bool = True,
        client=None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.use_fallbacks = use_fallbacks
        self._client = client if client is not None else _build_client(api_key)

    # -- request construction ------------------------------------------------

    def _payload(self, request: GMRequest) -> dict:
        model = request.model or self.model
        system: list[dict] = [{"type": "text", "text": request.system}]
        if request.cache_system:
            # Breakpoint on the first block only. Caching is a prefix match, so this
            # caches the session-stable instructions and nothing after them — campaign
            # state goes in a second, uncached block, and turn content stays in
            # `messages`. A canon write then re-reads one block instead of all of them.
            system[0]["cache_control"] = {"type": "ephemeral"}
        if request.system_volatile:
            system.append({"type": "text", "text": request.system_volatile})

        payload: dict = {
            "model": model,
            "max_tokens": request.max_tokens or self.max_tokens,
            "system": system,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
        }
        effort = request.effort or self.effort
        if effort:
            payload["output_config"] = {"effort": effort}
        return payload

    def _stream_kwargs(self, payload: dict) -> tuple[dict, bool]:
        """Add refusal fallbacks when the model is one that can decline."""
        if self.use_fallbacks and _supports_fallbacks(payload["model"]):
            return {**payload, "betas": [FALLBACK_BETA], "fallbacks": "default"}, True
        return payload, False

    # -- the call ------------------------------------------------------------

    def generate(
        self,
        request: GMRequest,
        on_text: Callable[[str], None] | None = None,
    ) -> GMResponse:
        payload, beta = self._stream_kwargs(self._payload(request))
        surface = self._client.beta.messages if beta else self._client.messages

        started = time.monotonic()
        try:
            with surface.stream(**payload) as stream:
                for chunk in stream.text_stream:
                    if on_text is not None and chunk:
                        on_text(chunk)
                message = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - re-raised as our own error below
            raise _translate(exc) from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        return _to_response(message, call_id=request.call_id or new_call_id(), duration_ms=duration_ms)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


# --- helpers ---------------------------------------------------------------


def _build_client(api_key: str | None):
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise GMBackendError(
            "the `api` backend needs the anthropic SDK — `pip install anthropic`, "
            "or start the session in subscription mode (`--billing subscription`)."
        ) from exc

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise GMBackendError(
            "no ANTHROPIC_API_KEY. Put it in .env (gitignored) or switch to "
            "`--billing subscription`."
        )
    return anthropic.Anthropic(api_key=key)


#: Models that accept the server-side `fallbacks` parameter. Verified against the live
#: API 2026-08-04: `claude-sonnet-5` returns 400 "does not support the `fallbacks`
#: parameter", so this list is narrower than the set of models that can *refuse*.
#: Refusal handling is unconditional; only the fallback opt-in is gated.
FALLBACK_MODELS = ("opus-5", "fable-5", "mythos-5")


def _supports_fallbacks(model: str) -> bool:
    return any(marker in model for marker in FALLBACK_MODELS)


def _to_response(message, call_id: str, duration_ms: int) -> GMResponse:
    stop_reason = getattr(message, "stop_reason", None)
    refused = stop_reason == "refusal"

    text = "".join(
        block.text
        for block in getattr(message, "content", []) or []
        if getattr(block, "type", None) == "text"
    )

    raw_usage = getattr(message, "usage", None)
    usage = Usage(
        input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
        output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(raw_usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0) or 0,
    )

    category = None
    details = getattr(message, "stop_details", None)
    if refused and details is not None:
        category = getattr(details, "category", None)

    return GMResponse(
        text=text,
        model=getattr(message, "model", "") or "",
        usage=usage,
        stop_reason=stop_reason,
        call_id=call_id,
        refused=refused,
        refusal_category=category,
        duration_ms=duration_ms,
    )


def _translate(exc: Exception) -> Exception:
    """Map SDK exceptions to something the turn loop can act on.

    Ordered most-specific first; the retryable cases keep their own type so a caller can
    back off, while the rest become GMBackendError with an actionable message.
    """
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return exc

    if isinstance(exc, anthropic.AuthenticationError):
        return GMBackendError("Anthropic rejected the API key — check .env.")
    if isinstance(exc, anthropic.NotFoundError):
        return GMBackendError(
            f"model not found: {exc}. Model ids live in config.yaml; check for a typo."
        )
    if isinstance(exc, anthropic.PermissionDeniedError):
        return GMBackendError(f"the API key lacks permission for this model: {exc}")
    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError)):
        return exc  # retryable — let the caller decide
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return exc  # retryable
    if isinstance(exc, anthropic.APIStatusError):
        return GMBackendError(f"Anthropic API error {exc.status_code}: {exc}")
    return exc
