from __future__ import annotations

from datetime import datetime
from typing import Any, Self

import msgspec

from .common import Model, to_records
from .coverage import Coverage
from .entrant import Entrant
from .enums import MarketKey, SourceKind
from .event import Event
from .odds import Odds
from .source import Source
from .stream import (
    CoverageFrame,
    EntrantFrame,
    EventFrame,
    OddsFrame,
    OddsSetFrame,
    StreamFrame,
)


def _key(item: Any, attr: str) -> Any:
    if attr == "coverage":
        return (item.key, item.places_paid, item.source_id)
    return item.id


def _upsert(owner: Any, attr: str, row: Any, key: Any) -> bool:
    """Replace the item with `key` in `owner.<attr>`, or append it.

    The position index lives in the instance `__dict__`, outside the wire
    fields, and is rebuilt whenever the list was changed behind its back.
    """
    items: list[Any] = getattr(owner, attr)
    index: dict[Any, int] | None = owner.__dict__.get(attr)
    pos = index.get(key) if index is not None else None
    if (
        index is None
        or (pos is not None and (pos >= len(items) or _key(items[pos], attr) != key))
        or (pos is None and len(index) != len(items))
    ):
        index = {_key(item, attr): i for i, item in enumerate(items)}
        owner.__dict__[attr] = index
        pos = index.get(key)
    if pos is None:
        index[key] = len(items)
        items.append(row)
        return True
    if items[pos] == row:
        return False
    items[pos] = row
    return True


class StreamContinuation(Model):
    """Exact server-issued scope for following a REST snapshot.

    Carries the cursor *and* the filters that produced it. Filters are part of
    a cursor's identity, so `client.follow()` replays these rather than asking
    the caller to restate them — restating them is how they drift and how you
    earn a `cursor_scope_changed`.

    An event snapshot scopes by `event`; a scope snapshot may scope by `sport`,
    `country`, `meeting` or `venue` instead, so no single filter is guaranteed.

    `url` is the `/v2/stream` path and query that follows this snapshot, with
    `cursor` and `snapshot=none` already set — for a client that is not this
    SDK, or one appending stream-only options such as `type` or `compress`.
    `client.follow()` sends the same request. It is None only on a
    continuation built by hand.
    """

    cursor: str
    event: list[str] = []
    source: list[str] = []
    sport: list[str] = []
    country: list[str] = []
    meeting: list[str] = []
    venue: list[str] = []
    key: list[str] = []
    entrant: list[str] = []
    start_from: str | None = None
    start_to: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.cursor.strip():
            raise ValueError("stream.cursor must be non-empty")

    @classmethod
    def from_json(cls, value: bytes | str) -> Self:
        """Restore a continuation persisted with :meth:`to_json`."""
        return msgspec.json.decode(value, type=cls)


class ScopeSnapshot(Model):
    """One page of current state for a filter scope, plus the stream handoff.

    How to start anything broader than a single race:

    ```python
    scope = RacingScope(sport="thoroughbred", country="au")
    snap = client.snapshot(scope)
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


class PriceSummary(Model):
    key: MarketKey
    source_kind: SourceKind
    best: float
    median: float
    source_count: int
    latest_checked_at: datetime
    oldest_checked_at: datetime
    places_paid: int | None = None
    best_sources: list[Source] = []


class RunnerPrices(Model):
    entrant_id: str
    name: str
    number: int
    prices: list[PriceSummary] = []


class EventSnapshot(Model, dict=True, gc=True):
    """One event's full card or compact summary.

    Only cards with `stream` can be passed to `client.follow()`. Keep an ordinary
    full snapshot current by applying live frames to it:

    ```python
    card = client.events.snapshot(event_id)
    with client.follow(card) as live:
        for frame in live:
            if card.apply(frame):
                print(card.best_price(card.entrants[0]))
    ```
    """

    event: Event
    stream: StreamContinuation | None = None
    entrants: list[Entrant] = []
    odds: list[Odds] = []
    coverage: list[Coverage] = []
    summary: list[RunnerPrices] = []
    max_age: int | None = None

    def quotes(
        self,
        entrant: Entrant | str | None = None,
        *,
        market: MarketKey = "win",
        source: str | None = None,
    ) -> list[Odds]:
        """Available, confirmed quotes. Legacy responses without confirmation remain usable.

        For an age-bounded comparison use events.snapshot(view="summary").
        Stream clocks are not heartbeats, so do not infer check age from ticks.
        """
        entrant_id = entrant.id if isinstance(entrant, Entrant) else entrant
        out: list[Odds] = []
        for quote in self.odds:
            if quote.state != "available" or quote.confirmation not in (None, "confirmed"):
                continue
            if quote.price is None:
                continue
            if quote.key != market:
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

    def apply(self, frame: StreamFrame) -> bool:
        """Merge one live frame into this card. Returns True if it changed anything.

        Odds, entrants and coverage are upserted by identity; an `event` frame
        updates status and times. Frames for another event, control frames and
        frames this SDK does not model are ignored. Each upsert is O(1).
        """
        if isinstance(frame, OddsFrame):
            return self._upsert_odds(frame.data)
        if isinstance(frame, OddsSetFrame):
            changed = False
            for row in frame.data.items:
                changed = self._upsert_odds(row) or changed
            return changed
        if isinstance(frame, EntrantFrame):
            row = frame.data
            return row.event_id == self.event.id and _upsert(self, "entrants", row, row.id)
        if isinstance(frame, CoverageFrame):
            row = frame.data
            key = (row.key, row.places_paid, row.source_id)
            return row.event_id == self.event.id and _upsert(self, "coverage", row, key)
        if isinstance(frame, EventFrame):
            patch = frame.data
            if patch.id != self.event.id:
                return False
            updates: dict[str, Any] = {"status": patch.status}
            if patch.start_at is not None:
                updates["start_at"] = patch.start_at
            if patch.updated_at is not None:
                updates["updated_at"] = patch.updated_at
            event = msgspec.structs.replace(self.event, **updates)
            if event == self.event:
                return False
            self.event = event
            return True
        return False

    def _upsert_odds(self, row: Odds) -> bool:
        return row.event_id == self.event.id and _upsert(self, "odds", row, row.id)

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
