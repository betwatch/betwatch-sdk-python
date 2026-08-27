from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeVar, cast

import msgspec

from .._compat import unknown_value_coercer
from .common import Model
from .coverage import Coverage
from .entrant import Entrant
from .enums import EventStatus, MarketKey
from .odds import Odds

_M = TypeVar("_M")


class StreamEvent(Model):
    """Lightweight event payload on the live stream (not the full REST Event)."""

    id: str
    status: EventStatus
    start_at: datetime | None = None
    updated_at: datetime | None = None


class StreamCursor(Model):
    cursor: str


class StreamResync(Model):
    reason: str


class StreamError(Model):
    code: str
    detail: str
    trace_id: str | None = None


class ReadyFrame(Model):
    data: StreamCursor
    cursor: str
    type: Literal["ready"] = "ready"


class SyncFrame(Model):
    data: StreamCursor
    cursor: str
    type: Literal["sync"] = "sync"


class EventFrame(Model):
    data: StreamEvent
    cursor: str
    type: Literal["event"] = "event"


class EntrantFrame(Model):
    data: Entrant
    cursor: str
    type: Literal["entrant"] = "entrant"


class OddsFrame(Model):
    data: Odds
    cursor: str
    type: Literal["odds"] = "odds"


class OddsSet(Model):
    """Snapshot-only coalesced odds for one win or place. Each item is a live Odds row."""

    event_id: str
    key: MarketKey
    places_paid: int | None = None
    items: list[Odds] = []


class OddsSetFrame(Model):
    data: OddsSet
    cursor: str
    type: Literal["odds_set"] = "odds_set"


class CoverageFrame(Model):
    data: Coverage
    cursor: str
    type: Literal["coverage"] = "coverage"


class UnknownFrame(Model):
    """Forward-compatible frame the SDK does not yet type."""

    cursor: str
    type: Literal["unknown"] = "unknown"
    data: Any = None
    name: str = "unknown"


StreamFrame = (
    ReadyFrame
    | SyncFrame
    | EventFrame
    | EntrantFrame
    | OddsFrame
    | OddsSetFrame
    | CoverageFrame
    | UnknownFrame
)


def _convert(raw: Any, model: type[_M]) -> _M:
    """Same forward-compat coercion the REST decoder applies.

    A frame carrying a vocabulary value newer than this SDK must not kill
    a live stream.
    """
    coerce = unknown_value_coercer(model)
    return msgspec.convert(coerce(raw) if coerce else raw, type=model)


def frame_for_event(event: str, cursor: str, payload: Any) -> StreamFrame:
    raw = payload or {}
    if event == "ready":
        return ReadyFrame(data=_convert(raw, StreamCursor), cursor=cursor)
    if event == "sync":
        return SyncFrame(data=_convert(raw, StreamCursor), cursor=cursor)
    if event == "event":
        return EventFrame(data=_convert(raw, StreamEvent), cursor=cursor)
    if event == "entrant":
        return EntrantFrame(data=_convert(raw, Entrant), cursor=cursor)
    if event == "odds":
        return OddsFrame(data=_convert(raw, Odds), cursor=cursor)
    if event == "odds_set":
        return OddsSetFrame(data=_convert(raw, OddsSet), cursor=cursor)
    if event == "coverage":
        return CoverageFrame(data=_convert(raw, Coverage), cursor=cursor)
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
