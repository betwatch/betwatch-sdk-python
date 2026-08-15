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


class EventSnapshot(Model):
    """REST bootstrap for one event. Pass `cursor` to `client.follow(this)`."""

    event: Event
    cursor: str | None = None
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

    def price(self, entrant: Entrant | str, source: str, *, market: MarketKey = "win") -> float | None:
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
