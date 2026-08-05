"""`subscription` adapter — headless Claude Code under the household Max login (D-004).

**The auth trap this adapter exists to avoid.** Credential resolution is
`ANTHROPIC_API_KEY` -> `ANTHROPIC_AUTH_TOKEN` -> stored claude.ai OAuth login. The API
key wins. Since `.env` holds a key for the `api` adapter, a naive `claude -p` in this
process would silently bill the metered key while the CLI cheerfully reported
"subscription mode" — spending against the console cap and defeating the entire point of
the D-004 toggle. Verified on kelly-pc 2026-08-04: with the key present, a four-token
reply cost $0.15 of API spend and Claude Code warned that the claude.ai login was being
ignored.

So the child process gets an environment with the metered credentials **removed**, which
lets Claude Code fall through to the stored OAuth login it already refreshes itself. We
do not read `~/.claude/.credentials.json`: copying a refresh token into our own process
would duplicate a secret and fight the refresh cycle. `auth_token` is available for the
case where a token should be pinned explicitly.

**Cost caveat.** Headless Claude Code carries its own system prompt and tool
definitions — measured at ~33-40k tokens per invocation on kelly-pc. That is charged to
the weekly pool rather than in dollars, but the `would_have_cost` figure it implies is
much larger than the equivalent bare API call. See PROGRESS.md.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Callable

from dndc.models.base import (
    DEFAULT_MAX_TOKENS,
    GMBackend,
    GMBackendError,
    GMRequest,
    GMResponse,
    Role,
    Usage,
    new_call_id,
)

#: Credentials that outrank the stored claude.ai login and must not reach the child.
METERED_ENV_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

THROTTLE_WARNING = (
    "subscription mode draws on the weekly Max pool — a long session can run it dry "
    "mid-scene. Switch with `--billing api` if that would spoil the evening."
)

DEFAULT_TIMEOUT_SECONDS = 300


class SubscriptionBackend(GMBackend):
    """GM seat over `claude -p`, billed to the subscription rather than the API key."""

    name = "subscription"

    def __init__(
        self,
        model: str,
        executable: str = "claude",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        auth_token: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess] | None = None,
    ) -> None:
        self.model = model
        self.executable = executable
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.auth_token = auth_token
        self._run = runner or subprocess.run

    # -- environment ---------------------------------------------------------

    def child_env(self) -> dict[str, str]:
        """The child's environment, with metered credentials stripped.

        This is the load-bearing part of the adapter; it is public and tested directly.
        """
        env = {k: v for k, v in os.environ.items() if k not in METERED_ENV_VARS}
        if self.auth_token:
            env["ANTHROPIC_AUTH_TOKEN"] = self.auth_token
        return env

    def command(self, request: GMRequest) -> list[str]:
        command = [
            self.executable,
            "-p",
            _flatten(request),
            "--output-format",
            "json",
            "--model",
            request.model or self.model,
        ]
        if request.system:
            # Replace Claude Code's default system prompt rather than appending to it —
            # the GM persona is the whole prompt, and replacing trims the payload.
            command += ["--system-prompt", request.system]
        return command

    # -- the call ------------------------------------------------------------

    def generate(
        self,
        request: GMRequest,
        on_text: Callable[[str], None] | None = None,
    ) -> GMResponse:
        if shutil.which(self.executable) is None and self._run is subprocess.run:
            raise GMBackendError(
                f"`{self.executable}` is not on PATH — subscription mode needs the "
                f"Claude Code CLI. Use `--billing api` instead."
            )

        started = time.monotonic()
        try:
            completed = self._run(
                self.command(request),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=self.child_env(),
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired as exc:
            raise GMBackendError(
                f"`{self.executable} -p` timed out after {self.timeout}s"
            ) from exc
        except OSError as exc:
            raise GMBackendError(f"could not run `{self.executable}`: {exc}") from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        if completed.returncode != 0:
            raise GMBackendError(
                f"`{self.executable} -p` exited {completed.returncode}: "
                f"{(completed.stderr or '').strip()[:400]}"
            )

        payload = _parse(completed.stdout)
        if payload.get("is_error"):
            raise GMBackendError(
                f"claude reported an error: {payload.get('result') or payload.get('subtype')}"
            )

        text = payload.get("result") or ""
        if on_text is not None and text:
            # Headless mode returns the whole turn at once; emit it as a single chunk so
            # callers can use one code path for both adapters.
            on_text(text)

        return GMResponse(
            text=text,
            model=request.model or self.model,
            usage=_usage(payload.get("usage") or {}),
            stop_reason=payload.get("stop_reason"),
            call_id=new_call_id(),
            reported_usd=payload.get("total_cost_usd"),
            duration_ms=payload.get("duration_ms") or duration_ms,
        )


# --- helpers ---------------------------------------------------------------


def _flatten(request: GMRequest) -> str:
    """Render the conversation into one prompt string.

    `claude -p` takes a single prompt, not a message array, so history is labelled
    inline. Phase 2's ledger-backed prompt builder produces the bulk of this anyway.
    """
    if not request.messages:
        return ""
    if len(request.messages) == 1 and request.messages[0].role is Role.USER:
        return request.messages[0].content
    lines = []
    for message in request.messages:
        label = "Player" if message.role is Role.USER else "GM"
        lines.append(f"{label}: {message.content}")
    return "\n\n".join(lines)


def _parse(stdout: str) -> dict:
    """Pull the result object out of stdout.

    Claude Code may print warnings before the JSON, so the first `{`-leading line is
    taken rather than assuming the whole of stdout parses.
    """
    text = (stdout or "").strip()
    if not text:
        raise GMBackendError("`claude -p` produced no output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise GMBackendError(f"could not parse `claude -p` output: {text[:200]}")


def _usage(raw: dict) -> Usage:
    return Usage(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_read_tokens=int(raw.get("cache_read_input_tokens") or 0),
        cache_write_tokens=int(raw.get("cache_creation_input_tokens") or 0),
    )
