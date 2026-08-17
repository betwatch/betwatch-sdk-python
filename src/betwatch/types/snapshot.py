from __future__ import annotations

from typing import Any

from .common import Model, to_records
from .coverage import Coverage
from .entrant import Entrant
from .enums import MarketKey
from .event import Event
from .market import Market
from .odds import Odds
from .outcome import Outcome


class StreamContinuation(Model):
    """Exact server-issued scope for following a REST snapshot.

    Carries the cursor *and* the filters that produced it. Filters are part of
    a cursor's identity, so `client.follow()` replays these rather than asking
    the caller to restate them — restating them is how they drift and how you
    earn a `cursor_scope_changed`.

    An event snapshot scopes by `event`; a scope snapshot may scope by `sport`,
    `country`, `meeting` or `venue` instead, so no single filter is guaranteed.
    """

    cursor: str
    event: list[str] = []
    source: list[str] = []
    sport: list[str] = []
    country: list[str] = []
    meeting: list[str] = []
    venue: list[str] = []
    start_from: str | None = None
    start_to: str | None = None

    def __post_init__(self) -> None:
        if not self.cursor.strip():
            raise ValueError("stream.cursor must be non-empty")


class ScopeSnapshot(Model):
    """One page of current state for a filter scope, plus the stream handoff.

    How to start anything broader than a single race:

    ```python
    snap = client.snapshot(sport="thoroughbred", country="au")
    with client.follow(snap) as live:
        ...
    ```

    Every page returns the same `stream.cursor`, captured before the first page
    was read, so paging to the end and then following cannot miss a change to a
    race read earlier. Follow from any page.
    """

    stream: StreamContinuation
    events: list[Event] = []
    entrants: list[Entrant] = []
    markets: list[Market] = []
    outcomes: list[Outcome] = []
    odds: list[Odds] = []
    coverage: list[Coverage] = []
    next: str | None = None
    previous: str | None = None

    def __iter__(self):
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)

    def to_records(self) -> list[dict[str, Any]]:
        return to_records(self.odds)


class EventSnapshot(Model):
    """REST bootstrap for one event. Pass this object to `client.follow()`."""

    stream: StreamContinuation
    event: Event
    entrants: list[Entrant] = []
    markets: list[Market] = []
    outcomes: list[Outcome] = []
    odds: list[Odds] = []
    coverage: list[Coverage] = []

    def quotes(
        self,
        entrant: Entrant | str | None = None,
        *,
        market: MarketKey = "win",
        source: str | None = None,
    ) -> list[Odds]:
        """Current priced quotes. Defaults to the win market."""
        market_ids = {row.id for row in self.markets if row.key == market}
        entrant_id = entrant.id if isinstance(entrant, Entrant) else entrant
        out: list[Odds] = []
        for quote in self.odds:
            if quote.price is None:
                continue
            if market_ids and quote.market_id not in market_ids:
                continue
            if entrant_id and quote.entrant_id != entrant_id:
                continue
            if source and quote.source.id != source:
                continue
            out.append(quote)
        return out

    def best_price(self, entrant: Entrant | str, *, market: MarketKey = "win") -> float | None:
        prices = [quote.price for quote in self.quotes(entrant, market=market) if quote.price]
        return max(prices) if prices else None

    def lowest_price(self, entrant: Entrant | str, *, market: MarketKey = "win") -> float | None:
        prices = [quote.price for quote in self.quotes(entrant, market=market) if quote.price]
        return min(prices) if prices else None

    def price(
        self, entrant: Entrant | str, source: str, *, market: MarketKey = "win"
    ) -> float | None:
        quotes = self.quotes(entrant, market=market, source=source)
        return quotes[0].price if quotes else None

    def to_records(self) -> list[dict[str, Any]]:
        """One row per current odds quote, denormalized for a DataFrame."""
        names = {entrant.id: entrant.name for entrant in self.entrants}
        rows: list[dict[str, Any]] = []
        for quote in self.odds:
            row = to_records(quote)[0]
            row["eventName"] = self.event.name
            row["startAt"] = self.event.start_at
            row["entrantName"] = names.get(quote.entrant_id or "")
            rows.append(row)
        return rows
