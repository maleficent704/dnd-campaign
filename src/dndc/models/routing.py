"""Choosing which Ollama host serves a seat (P4.3, OD-5).

Two endpoints have been registered since day one — toto-llm (dual 3090) and sam-pc, the
second declared before it existed precisely so nothing would have to be rewired when it
arrives. This is the layer that picks between them.

**A route is only good if the host has the model.** Liveness alone is not enough: sam-pc
answers long before it has a 70B pulled, and an endpoint that is up but empty is the worst
kind of fallback because it fails at generate time, halfway into a scene. So the probe
reads `/api/tags` and checks for the model by name, and an endpoint without it is not a
candidate.

**Nothing here ever substitutes a different model.** If no endpoint has what the seat asks
for, this raises and names what it tried. Quietly voicing an NPC with whatever happened to
be loaded would be the same class of error as hardcoding a model name — the config says
what runs (OD-5), and a log that says `llama3.3:70b` while an 8B did the talking makes every
later measurement a lie.

**Resolution is cached.** Probing costs a round trip, and an NPC that probes before every
line adds that to every line. The router resolves once and holds it; `resolve(force=True)`
re-probes, which is what a caller does after a call fails rather than before every call
that might.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping

from dndc.config import Config, OllamaSeat

#: Long enough for a sleeping host to answer, short enough not to hold up a scene. A probe
#: is a `GET /api/tags`, which is cheap even on a box that is busy generating.
PROBE_TIMEOUT_SECONDS = 5


class RoutingError(RuntimeError):
    """No endpoint can serve this seat, and the message says what was tried."""


@dataclass(frozen=True)
class Endpoint:
    """A registered Ollama host. `name` is what a log and a human should say."""

    name: str
    url: str


@dataclass(frozen=True)
class Route:
    """Where a seat's calls are going, and whether that was the first choice."""

    endpoint: Endpoint
    model: str
    #: True when the seat's own configured endpoint could not serve it. Logged rather
    #: than merely acted on: a silent fallback changes latency and quantization mid-session,
    #: which surfaces in Phase 7 as variance nobody can explain.
    fell_back: bool = False
    #: Why the preferred endpoint was passed over, in a sentence. Empty when it was used.
    reason: str = ""


class OllamaRouter:
    """Resolves a seat to an endpoint that actually has its model."""

    def __init__(
        self,
        endpoints: Mapping[str, str],
        probe: Callable[[str], frozenset[str] | None] | None = None,
        timeout: int = PROBE_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoints = dict(endpoints)
        self.timeout = timeout
        self._probe = probe or self._models_at
        self._routes: dict[tuple[str, str], Route] = {}

    @classmethod
    def for_config(cls, config: Config, **kwargs) -> OllamaRouter:
        return cls(config.ollama_endpoints, **kwargs)

    # --- resolution --------------------------------------------------------

    def candidates(self, seat: OllamaSeat) -> list[Endpoint]:
        """The seat's own endpoint first, then every other registered one.

        The seat's URL is matched against the registry so a route can be *named* — a log
        saying "sam-pc" is worth more than one saying a bare IP, and the registry is the
        only place those names exist.
        """
        seat_url = seat.endpoint.rstrip("/")
        named = {url.rstrip("/"): name for name, url in self.endpoints.items()}
        first = Endpoint(name=named.get(seat_url, "seat"), url=seat_url)
        rest = [
            Endpoint(name=name, url=url.rstrip("/"))
            for name, url in self.endpoints.items()
            if url.rstrip("/") != seat_url
        ]
        return [first, *rest]

    def resolve(self, seat: OllamaSeat, force: bool = False) -> Route:
        """Pick an endpoint for this seat, probing each in turn.

        `force` re-probes a cached answer — what a caller does *after* a failure, not
        before every call that might have one.
        """
        key = (seat.endpoint.rstrip("/"), seat.model)
        if not force and key in self._routes:
            return self._routes[key]

        tried: list[str] = []
        for index, endpoint in enumerate(self.candidates(seat)):
            models = self._probe(endpoint.url)
            if models is None:
                tried.append(f"{endpoint.name} ({endpoint.url}): unreachable")
                continue
            if not _has_model(models, seat.model):
                held = ", ".join(sorted(models)) or "no models"
                tried.append(f"{endpoint.name} ({endpoint.url}): has {held}")
                continue

            route = Route(
                endpoint=endpoint,
                model=seat.model,
                fell_back=index > 0,
                reason="; ".join(tried) if index > 0 else "",
            )
            self._routes[key] = route
            return route

        raise RoutingError(
            f"no Ollama endpoint can serve {seat.model!r}. Tried: {'; '.join(tried)}. "
            f"Endpoints live in config.yaml under `ollama_endpoints`; check the host is "
            f"up and the model is pulled (`ollama pull {seat.model}`)."
        )

    # --- the probe ---------------------------------------------------------

    def _models_at(self, url: str) -> frozenset[str] | None:
        """Model names an endpoint holds, or None when it cannot be reached.

        None and the empty set are different answers and are kept different: a host that
        is down might come back, and a host that is up with nothing pulled needs a person
        to go and pull something. The error message says which.
        """
        request = urllib.request.Request(f"{url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None
        return frozenset(
            entry.get("name", "") for entry in raw.get("models", []) if entry.get("name")
        )


def _has_model(models: frozenset[str], wanted: str) -> bool:
    """Ollama reports `llama3.3:70b`; a config may omit the tag and mean `:latest`."""
    if wanted in models:
        return True
    return not ":" in wanted and f"{wanted}:latest" in models
