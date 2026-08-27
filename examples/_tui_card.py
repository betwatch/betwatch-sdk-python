from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from msgspec.structs import replace

from _tui_format import format_price, source_label, source_sort_key
from betwatch.types.entrant import Entrant
from betwatch.types.event import Event
from betwatch.types.odds import Odds
from betwatch.types.snapshot import EventSnapshot
from betwatch.types.stream import (
    CoverageFrame,
    EntrantFrame,
    EventFrame,
    OddsFrame,
    OddsSetFrame,
    StreamEvent,
    StreamFrame,
)

_T = TypeVar("_T")


@dataclass(frozen=True)
class GridColumn:
    key: str
    label: str
    source_id: str | None = None


@dataclass(frozen=True)
class GridCell:
    text: str
    price: float | None = None
    best: bool = False


@dataclass(frozen=True)
class GridRow:
    entrant_id: str
    number: str
    name: str
    scratched: bool
    vacant: bool
    cells: tuple[GridCell, ...]


@dataclass(frozen=True)
class RaceGrid:
    columns: tuple[GridColumn, ...]
    rows: tuple[GridRow, ...]
    priced: int


def quote_price(quote: Odds) -> float | None:
    if quote.price is not None:
        return quote.price
    if quote.exchange and quote.exchange.back:
        return quote.exchange.back[0].price
    return None


def _upsert(items: list[_T], incoming: _T, key: Callable[[_T], object]) -> None:
    token = key(incoming)
    for index, item in enumerate(items):
        if key(item) == token:
            items[index] = incoming
            return
    items.append(incoming)


def _odds_key(quote: Odds) -> tuple[str, str, str, str]:
    return (quote.id, quote.key, quote.source.id, quote.entrant_id or "")


def apply_stream_event(event: Event, patch: StreamEvent) -> Event:
    updates: dict[str, object] = {"status": patch.status}
    if patch.start_at is not None:
        updates["start_at"] = patch.start_at
    if patch.updated_at is not None:
        updates["updated_at"] = patch.updated_at
    return replace(event, **updates)


def apply_event_list(events: list[Event], patch: StreamEvent) -> list[Event]:
    out: list[Event] = []
    found = False
    for event in events:
        if event.id == patch.id:
            out.append(apply_stream_event(event, patch))
            found = True
        else:
            out.append(event)
    return out if found else events


def apply_frame(card: EventSnapshot, frame: StreamFrame) -> bool:
    """Merge a live frame into the snapshot. Returns True if anything changed."""
    if isinstance(frame, EventFrame):
        card.event = apply_stream_event(card.event, frame.data)
        return True
    if isinstance(frame, EntrantFrame):
        _upsert(card.entrants, frame.data, key=lambda row: row.id)
        return True
    if isinstance(frame, OddsFrame):
        _upsert(card.odds, frame.data, key=_odds_key)
        return True
    if isinstance(frame, OddsSetFrame):
        changed = False
        for row in frame.data.items:
            _upsert(card.odds, row, key=_odds_key)
            changed = True
        return changed
    if isinstance(frame, CoverageFrame):
        _upsert(
            card.coverage,
            frame.data,
            key=lambda row: (row.event_id, row.key, row.places_paid, row.source_id),
        )
        return True
    return False


def sort_entrants(entrants: list[Entrant]) -> list[Entrant]:
    def key(entrant: Entrant) -> tuple[int, int, str]:
        if entrant.vacant:
            group = 2
        elif entrant.scratched:
            group = 1
        else:
            group = 0
        return (group, entrant.number, entrant.name)

    return sorted(entrants, key=key)


def priced_quotes(card: EventSnapshot, market: str = "win") -> list[Odds]:
    key = market.lower()
    out: list[Odds] = []
    for quote in card.odds:
        if quote.key != key:
            continue
        if quote_price(quote) is None:
            continue
        out.append(quote)
    return out


def source_columns(card: EventSnapshot, market: str = "win") -> list[GridColumn]:
    seen: dict[str, str] = {}
    for quote in priced_quotes(card, market):
        seen.setdefault(quote.source.id, quote.source.name)
    columns = [
        GridColumn(key=source_id, label=source_label(source_id, name), source_id=source_id)
        for source_id, name in seen.items()
    ]
    columns.sort(key=lambda column: source_sort_key(column.key))
    return [
        GridColumn(key="num", label="#"),
        GridColumn(key="runner", label="Runner"),
        GridColumn(key="best", label="Best"),
        *columns,
    ]


def build_grid(card: EventSnapshot, market: str = "win") -> RaceGrid:
    columns = source_columns(card, market)
    source_keys = [column.key for column in columns if column.source_id]
    rows: list[GridRow] = []
    priced = 0
    for entrant in sort_entrants(card.entrants):
        by_source: dict[str, float] = {}
        for quote in priced_quotes(card, market):
            if quote.entrant_id != entrant.id:
                continue
            price = quote_price(quote)
            if price is None:
                continue
            by_source[quote.source.id] = price
        best = max(by_source.values()) if by_source else None
        if by_source:
            priced += 1
        cells: list[GridCell] = [
            GridCell(text=format_price(best), price=best, best=best is not None),
        ]
        for source_id in source_keys:
            price = by_source.get(source_id)
            cells.append(
                GridCell(
                    text=format_price(price),
                    price=price,
                    best=price is not None and best is not None and price == best,
                )
            )
        number = "—" if entrant.vacant and not entrant.number else str(entrant.number or "—")
        name = "Vacant" if entrant.vacant else entrant.name
        if entrant.scratched:
            name = f"{name} (scr)"
        rows.append(
            GridRow(
                entrant_id=entrant.id,
                number=number,
                name=name,
                scratched=entrant.scratched,
                vacant=entrant.vacant,
                cells=tuple(cells),
            )
        )
    return RaceGrid(columns=tuple(columns), rows=tuple(rows), priced=priced)
