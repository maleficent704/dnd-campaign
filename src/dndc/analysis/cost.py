"""What an evening cost, read back off the log (P5.4).

Every model call in this project writes a `cost` row (D-008), and until now nothing read
them. This is the thing that reads them, and like everything else in `analysis/` it only
ever reads: an instrument that alters what it measures is not an instrument (P2.6).

Three rules, and all three are about not letting a total say more than it knows.

**Money and would-have-cost are never added together.** In subscription mode `usd` is what
the call *would* have cost at API rates, flagged `would_have_cost` — that is what makes the
D-004 toggle arguable rather than a matter of opinion. It is not a bill, and OD-16 goes
further: subscription figures measure headless Claude Code's harness rather than this
campaign, so they are not even comparable with the API ones. Two columns, never one.

**A local seat's cost is time.** toto-llm bills nothing and takes minutes, and a report that
printed `$0.00` beside the 70B and stopped would be lying by omission — the expensive thing
about the NPC tier has never been money. So latency is a first-class column, with the median
and the worst case rather than only a sum: one 62-second cold load inside twenty warm calls
is the finding, and a mean hides it.

**Unpriced calls are counted, not dropped.** A row with no `usd` is either a local seat or a
model missing from the pricing table in `config.yaml`. Both are real, and a total that
quietly skipped them would under-report the second one forever.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from dndc.logging import read_log
from dndc.schema.events import EventType

#: Display order. The seats in the order a turn uses them, then anything unrecognised —
#: a seat this build has never heard of is still worth showing, since the log outlives
#: the code that wrote it.
SEAT_ORDER = ("gm", "npc", "utility_interactive", "utility_batch")


@dataclass(frozen=True)
class SeatCost:
    """One seat's share of a session."""

    seat: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    #: Money actually spent — rows that carried a price and were not hypothetical.
    usd: float = 0.0
    #: What subscription-mode calls would have cost at API rates. Never added to `usd`.
    hypothetical_usd: float = 0.0
    #: Calls that carried no price at all: a local seat, or a model absent from the
    #: pricing table. Kept so a total can say what it does not cover.
    unpriced: int = 0
    #: Every measured wall-clock time, unsorted. Kept whole rather than pre-averaged
    #: because the distribution is the finding on a local seat.
    latencies: tuple[int, ...] = ()
    models: tuple[str, ...] = ()

    def __add__(self, other: SeatCost) -> SeatCost:
        if other.seat != self.seat:
            raise ValueError(f"cannot add {other.seat!r} to {self.seat!r}")
        return SeatCost(
            seat=self.seat,
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            usd=self.usd + other.usd,
            hypothetical_usd=self.hypothetical_usd + other.hypothetical_usd,
            unpriced=self.unpriced + other.unpriced,
            latencies=self.latencies + other.latencies,
            models=tuple(dict.fromkeys(self.models + other.models)),
        )

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def priced(self) -> int:
        return self.calls - self.unpriced

    @property
    def local(self) -> bool:
        """No money changed hands and none would have. The cost was the clock."""
        return self.usd == 0.0 and self.hypothetical_usd == 0.0

    @property
    def ms(self) -> int:
        return sum(self.latencies)

    @property
    def median_ms(self) -> int | None:
        if not self.latencies:
            return None
        return int(statistics.median(self.latencies))

    @property
    def slowest_ms(self) -> int | None:
        return max(self.latencies) if self.latencies else None


@dataclass(frozen=True)
class Summary:
    """The bottom line, with the parts that must not be conflated kept apart."""

    calls: int = 0
    usd: float = 0.0
    hypothetical_usd: float = 0.0
    unpriced: int = 0
    ms: int = 0

    @property
    def seconds(self) -> float:
        return self.ms / 1000


@dataclass(frozen=True)
class SessionCost:
    """One log's worth of calls."""

    path: Path | None = None
    session_id: str | None = None
    campaign: str | None = None
    #: Every billing mode the log's headers named. More than one means the process was
    #: restarted onto a different seat mid-evening (P5.2), which a single figure cannot
    #: describe and this report should not pretend to.
    billing: tuple[str, ...] = ()
    restarts: int = 0
    seats: dict[str, SeatCost] = field(default_factory=dict)

    @property
    def summary(self) -> Summary:
        return summarise(self.seats.values())

    @property
    def ordered(self) -> list[SeatCost]:
        return ordered_seats(self.seats)

    @property
    def empty(self) -> bool:
        return not self.seats


@dataclass(frozen=True)
class CampaignCost:
    """Several sessions, added up. A campaign to date."""

    campaign: str | None = None
    sessions: tuple[SessionCost, ...] = ()
    seats: dict[str, SeatCost] = field(default_factory=dict)

    @property
    def summary(self) -> Summary:
        return summarise(self.seats.values())

    @property
    def ordered(self) -> list[SeatCost]:
        return ordered_seats(self.seats)

    @property
    def empty(self) -> bool:
        return not self.seats


def read_session(path: Path | str) -> SessionCost:
    """Add up one log. A log with no cost rows is empty, not an error."""
    target = Path(path)
    seats: dict[str, SeatCost] = {}
    session_id: str | None = None
    campaign: str | None = None
    billing: list[str] = []
    headers = 0

    for event in read_log(target):
        if event.type is EventType.SESSION_META:
            headers += 1
            if session_id is None:
                session_id = event.session_id
                campaign = event.campaign
            if event.billing not in billing:
                billing.append(event.billing)
        elif event.type is EventType.COST:
            seats[event.seat] = seats.get(event.seat, SeatCost(seat=event.seat)) + _row(event)

    return SessionCost(
        path=target,
        session_id=session_id,
        campaign=campaign,
        billing=tuple(billing),
        restarts=max(headers - 1, 0),
        seats=seats,
    )


def read_campaign(paths: Iterable[Path | str], campaign: str | None = None) -> CampaignCost:
    """Every session of one campaign, added up.

    `campaign` filters by the name in `session_meta`. Logs from other campaigns — and the
    scratch ones every verification run leaves behind — are skipped rather than counted.
    """
    sessions: list[SessionCost] = []
    for path in paths:
        session = read_session(path)
        if session.empty:
            continue
        if campaign is not None and (session.campaign or "").casefold() != campaign.casefold():
            continue
        sessions.append(session)

    seats: dict[str, SeatCost] = {}
    for session in sessions:
        for name, seat in session.seats.items():
            seats[name] = seats.get(name, SeatCost(seat=name)) + seat
    return CampaignCost(campaign=campaign, sessions=tuple(sessions), seats=seats)


def summarise(seats: Iterable[SeatCost]) -> Summary:
    total = Summary()
    for seat in seats:
        total = replace(
            total,
            calls=total.calls + seat.calls,
            usd=total.usd + seat.usd,
            hypothetical_usd=total.hypothetical_usd + seat.hypothetical_usd,
            unpriced=total.unpriced + seat.unpriced,
            ms=total.ms + seat.ms,
        )
    return total


def ordered_seats(seats: Mapping[str, SeatCost]) -> list[SeatCost]:
    def rank(name: str) -> tuple[int, str]:
        return (SEAT_ORDER.index(name) if name in SEAT_ORDER else len(SEAT_ORDER), name)

    return [seats[name] for name in sorted(seats, key=rank)]


def logs_in(directory: Path | str) -> list[Path]:
    """Session logs, oldest first. Names are timestamps, so the sort is chronological."""
    return sorted(Path(directory).glob("*.jsonl"))


def latest_log(directory: Path | str) -> Path | None:
    found = logs_in(directory)
    return found[-1] if found else None


def _row(event) -> SeatCost:
    """One `cost` row as a one-call seat total.

    A row with `would_have_cost` set is a subscription call priced at API rates for the
    argument's sake; it is money that was not spent, and it goes in its own column. A row
    with no `usd` at all is a local seat or an unpriced model, and it is counted as such
    rather than as a zero — a zero would silently become part of a total that claimed to
    be complete.
    """
    hypothetical = event.usd if (event.usd is not None and event.would_have_cost) else 0.0
    spent = event.usd if (event.usd is not None and not event.would_have_cost) else 0.0
    return SeatCost(
        seat=event.seat,
        calls=1,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        cache_read_tokens=event.cache_read_tokens,
        cache_write_tokens=event.cache_write_tokens,
        usd=spent,
        hypothetical_usd=hypothetical,
        unpriced=1 if event.usd is None else 0,
        latencies=(event.latency_ms,) if event.latency_ms is not None else (),
        models=(event.model,) if event.model else (),
    )
