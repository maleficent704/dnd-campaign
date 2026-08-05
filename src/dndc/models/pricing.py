"""Cost telemetry (D-008) and the would-have-cost calculation (D-004).

Prices are **data**, in `config.yaml` — a rate change should be a config edit, not a
release. An unpriced model yields `None` rather than a guess: a wrong number in the
cost log is worse than a missing one, because Phase 7 will treat it as measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndc.models.base import Usage

TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens."""

    input: float
    output: float
    cache_write: float | None = None
    cache_read: float | None = None

    @property
    def effective_cache_write(self) -> float:
        """Anthropic's 5-minute cache write is 1.25x the input rate."""
        return self.cache_write if self.cache_write is not None else self.input * 1.25

    @property
    def effective_cache_read(self) -> float:
        """Cache reads are ~0.1x the input rate."""
        return self.cache_read if self.cache_read is not None else self.input * 0.10


def price_for(model: str, prices: dict[str, ModelPrice]) -> ModelPrice | None:
    """Look up a model's price, tolerating a dated-snapshot suffix.

    Backends sometimes report `claude-sonnet-5-20260115` where config says
    `claude-sonnet-5`; treating those as unpriced would silently blank the telemetry.
    """
    if model in prices:
        return prices[model]
    candidates = [key for key in prices if model.startswith(key)]
    if not candidates:
        return None
    return prices[max(candidates, key=len)]


def estimate_cost(
    usage: Usage, model: str, prices: dict[str, ModelPrice]
) -> float | None:
    """Dollar cost of one call, or None if the model has no configured price."""
    price = price_for(model, prices)
    if price is None:
        return None
    return (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_write_tokens * price.effective_cache_write
        + usage.cache_read_tokens * price.effective_cache_read
    ) / TOKENS_PER_MILLION


def load_prices(raw: dict) -> dict[str, ModelPrice]:
    """Build the price table from the `pricing:` block in config.yaml.

    Accepts either plain dicts or the typed `PriceEntry` models, so a caller can pass
    `config.pricing` straight through without unwrapping it first.
    """

    def field(entry, name: str):
        return entry.get(name) if isinstance(entry, dict) else getattr(entry, name, None)

    table = {}
    for model, entry in raw.items():
        write = field(entry, "cache_write")
        read = field(entry, "cache_read")
        table[model] = ModelPrice(
            input=float(field(entry, "input")),
            output=float(field(entry, "output")),
            cache_write=float(write) if write is not None else None,
            cache_read=float(read) if read is not None else None,
        )
    return table
