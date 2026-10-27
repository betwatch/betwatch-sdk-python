from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal, cast

import msgspec

from .._compat import decode_json
from .common import Model
from .coverage import Coverage
from .entrant import Entrant
from .enums import EventStatus, MarketKey
from .odds import Odds


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
    resync_token: str | None = None


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
    cursor: str | None = None
    type: Literal["event"] = "event"


class EntrantFrame(Model):
    data: Entrant
    cursor: str | None = None
    type: Literal["entrant"] = "entrant"


class OddsFrame(Model):
    data: Odds
    cursor: str | None = None
    type: Literal["odds"] = "odds"


class OddsSet(Model):
    """Snapshot-only coalesced odds for one win or place. Each item is a live Odds row."""

    event_id: str
    key: MarketKey
    places_paid: int | None = None
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

    cursor: str | None = None
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


def frame_for_event(event: str, cursor: str | None, payload: bytes) -> StreamFrame:
    """Decode one data frame. Unknown vocabulary values become `"unknown"`, the
    same forward-compat rule as REST: a newer value must not kill a live stream.
    """
    raw = payload or b"{}"
    if event == "odds":
        return OddsFrame(data=decode_json(raw, Odds), cursor=cursor)
    if event == "coverage":
        return CoverageFrame(data=decode_json(raw, Coverage), cursor=cursor)
    if event == "entrant":
        return EntrantFrame(data=decode_json(raw, Entrant), cursor=cursor)
    if event == "event":
        return EventFrame(data=decode_json(raw, StreamEvent), cursor=cursor)
    if event == "odds_set":
        return OddsSetFrame(data=decode_json(raw, OddsSet), cursor=cursor)
    if event == "ready":
        return ReadyFrame(data=decode_json(raw, StreamCursor), cursor=cursor or "")
    if event == "sync":
        return SyncFrame(data=decode_json(raw, StreamCursor), cursor=cursor or "")
    return UnknownFrame(
        data=msgspec.json.decode(payload) if payload else None, cursor=cursor, name=event
    )


def iter_odds(frame: StreamFrame) -> Iterator[Odds]:
    """Yield live-shaped Odds rows from a singleton tick or a snapshot set."""
    if isinstance(frame, OddsFrame):
        yield frame.data
    elif isinstance(frame, OddsSetFrame):
        yield from frame.data.items


def frame_name(frame: StreamFrame) -> str:
    if isinstance(frame, UnknownFrame):
        return frame.name
    return cast(str, frame.type)
