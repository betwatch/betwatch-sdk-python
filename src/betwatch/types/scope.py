"""Typed caller-owned filters for a racing snapshot and its live stream."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar, cast

from .enums import RequestMarket, RequestSport

_T = TypeVar("_T", bound=str)


def _many(value: _T | Sequence[_T] | None, *, name: str) -> tuple[_T, ...]:
    if value is None:
        return ()
    values = (cast(_T, value),) if isinstance(value, str) else tuple(value)
    if any("," in item for item in values):
        raise ValueError(f"{name} values must not contain commas")
    return values


def _time(value: datetime | str | None, *, name: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True, init=False)
class RacingScope:
    """Immutable filters shared by ``/events/snapshot`` and ``/stream``.

    A scope is caller intent, while ``StreamContinuation`` is the exact
    server-issued position used to resume it. The constructor accepts one value
    or a sequence, then stores tuples so a scope cannot change mid-flight.
    """

    sport: tuple[RequestSport, ...]
    country: tuple[str, ...]
    meeting: tuple[str, ...]
    event: tuple[str, ...]
    venue: tuple[str, ...]
    market: tuple[RequestMarket, ...]
    entrant: tuple[str, ...]
    source: tuple[str, ...]
    start_from: str | None
    start_to: str | None

    def __init__(
        self,
        *,
        sport: RequestSport | Sequence[RequestSport] | None = None,
        country: str | Sequence[str] | None = None,
        meeting: str | Sequence[str] | None = None,
        event: str | Sequence[str] | None = None,
        venue: str | Sequence[str] | None = None,
        market: RequestMarket | Sequence[RequestMarket] | None = None,
        entrant: str | Sequence[str] | None = None,
        source: str | Sequence[str] | None = None,
        start_from: datetime | str | None = None,
        start_to: datetime | str | None = None,
    ) -> None:
        object.__setattr__(self, "sport", _many(sport, name="sport"))
        object.__setattr__(self, "country", _many(country, name="country"))
        object.__setattr__(self, "meeting", _many(meeting, name="meeting"))
        object.__setattr__(self, "event", _many(event, name="event"))
        object.__setattr__(self, "venue", _many(venue, name="venue"))
        object.__setattr__(self, "market", _many(market, name="market"))
        object.__setattr__(self, "entrant", _many(entrant, name="entrant"))
        object.__setattr__(self, "source", _many(source, name="source"))
        object.__setattr__(self, "start_from", _time(start_from, name="start_from"))
        object.__setattr__(self, "start_to", _time(start_to, name="start_to"))

    def _stream_filters(self) -> dict[str, tuple[str, ...] | str | None]:
        return {
            "sport": self.sport,
            "country": self.country,
            "meeting": self.meeting,
            "event": self.event,
            "venue": self.venue,
            "market": self.market,
            "entrant": self.entrant,
            "source": self.source,
            "startFrom": self.start_from,
            "startTo": self.start_to,
        }

    @classmethod
    def _from_continuation(
        cls,
        *,
        sport: Sequence[str],
        country: Sequence[str],
        meeting: Sequence[str],
        event: Sequence[str],
        venue: Sequence[str],
        market: Sequence[str],
        entrant: Sequence[str],
        source: Sequence[str],
        start_from: str | None,
        start_to: str | None,
    ) -> RacingScope:
        """Replay server values verbatim, including values newer than this SDK."""
        return cls(
            sport=cast(Sequence[RequestSport], sport),
            country=country,
            meeting=meeting,
            event=event,
            venue=venue,
            market=cast(Sequence[RequestMarket], market),
            entrant=entrant,
            source=source,
            start_from=start_from,
            start_to=start_to,
        )
