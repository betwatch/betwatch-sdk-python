from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

import msgspec

from .common import Model
from .coverage import Coverage
from .entrant import Entrant
from .enums import EventStatus
from .market import Market
from .odds import Odds
from .outcome import Outcome


class StreamEvent(Model):
    """Lightweight event payload on the live stream (not the full REST Event)."""

    id: str
    status: EventStatus
    start_at: datetime | None = None
    updated_at: datetime | None = None


class StreamCursor(Model):
    cursor: str | None = None


class StreamResync(Model):
    reason: str | None = None


class ReadyFrame(Model):
    data: StreamCursor | None = None
    cursor: str | None = None
    type: Literal["ready"] = "ready"


class SyncFrame(Model):
    data: StreamCursor | None = None
    cursor: str | None = None
    type: Literal["sync"] = "sync"


class EventFrame(Model):
    data: StreamEvent
    cursor: str | None = None
    type: Literal["event"] = "event"


class EntrantFrame(Model):
    data: Entrant
    cursor: str | None = None
    type: Literal["entrant"] = "entrant"


class MarketFrame(Model):
    data: Market
    cursor: str | None = None
    type: Literal["market"] = "market"


class OutcomeFrame(Model):
    data: Outcome
    cursor: str | None = None
    type: Literal["outcome"] = "outcome"


class OddsFrame(Model):
    data: Odds
    cursor: str | None = None
    type: Literal["odds"] = "odds"


class OddsSet(Model):
    """Snapshot-only coalesced odds for one market. Each item is a live Odds row."""

    event_id: str
    market_id: str
    items: list[Odds] = []


class OddsSetFrame(Model):
    data: OddsSet
    cursor: str | None = None
    type: Literal["odds_set"] = "odds_set"


class CoverageFrame(Model):
    data: Coverage
    cursor: str | None = None
    type: Literal["coverage"] = "coverage"


class UnknownFrame(Model):
    """Forward-compatible frame the SDK does not yet type."""

    type: Literal["unknown"] = "unknown"
    data: Any = None
    cursor: str | None = None
    name: str = "unknown"


StreamFrame = (
    ReadyFrame
    | SyncFrame
    | EventFrame
    | EntrantFrame
    | MarketFrame
    | OutcomeFrame
    | OddsFrame
    | OddsSetFrame
    | CoverageFrame
    | UnknownFrame
)


def frame_for_event(event: str, cursor: str | None, payload: Any) -> StreamFrame:
    raw = payload or {}
    if event == "ready":
        return ReadyFrame(data=msgspec.convert(raw, type=StreamCursor), cursor=cursor)
    if event == "sync":
        return SyncFrame(data=msgspec.convert(raw, type=StreamCursor), cursor=cursor)
    if event == "event":
        return EventFrame(data=msgspec.convert(raw, type=StreamEvent), cursor=cursor)
    if event == "entrant":
        return EntrantFrame(data=msgspec.convert(raw, type=Entrant), cursor=cursor)
    if event == "market":
        return MarketFrame(data=msgspec.convert(raw, type=Market), cursor=cursor)
    if event == "outcome":
        return OutcomeFrame(data=msgspec.convert(raw, type=Outcome), cursor=cursor)
    if event == "odds":
        return OddsFrame(data=msgspec.convert(raw, type=Odds), cursor=cursor)
    if event == "odds_set":
        return OddsSetFrame(data=msgspec.convert(raw, type=OddsSet), cursor=cursor)
    if event == "coverage":
        return CoverageFrame(data=msgspec.convert(raw, type=Coverage), cursor=cursor)
    return UnknownFrame(data=payload, cursor=cursor, name=event)


def iter_odds(frame: StreamFrame):
    """Yield live-shaped Odds rows from a singleton tick or a snapshot set."""
    if isinstance(frame, OddsFrame):
        yield frame.data
    elif isinstance(frame, OddsSetFrame):
        yield from frame.data.items


def frame_name(frame: StreamFrame) -> str:
    if isinstance(frame, UnknownFrame):
        return frame.name
    return cast(str, frame.type)
