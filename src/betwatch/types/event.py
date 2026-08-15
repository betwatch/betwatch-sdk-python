from __future__ import annotations

from datetime import datetime

import msgspec

from .common import Model, Money
from .coverage import Coverage
from .enums import (
    LIVE_EVENT_STATUSES,
    DividendPool,
    EventStatus,
    ResultState,
    Sport,
    Surface,
)
from .page import Page


class Dividend(Model):
    pool: DividendPool
    amount_cents: int
    currency: str
    source_id: str
    entrant_ids: list[str] = []
    observed_at: datetime | None = None


class ResultPosition(Model):
    place: int
    entrant_ids: list[str] = []


class EventResult(Model):
    state: ResultState
    positions: list[ResultPosition] = []
    updated_at: datetime | None = None


class EventRacing(Model):
    race_number: int = 0
    distance_meters: int | None = None
    track_condition: str | None = None
    rail_position: str | None = None
    weather: str | None = None
    class_conditions: str | None = None
    race_class: str | None = None
    surface: Surface | None = None
    places_paid: int | None = None
    prize_money: Money | None = None
    dividends: list[Dividend] = []


class Event(Model):
    id: str
    sport: Sport
    name: str
    start_at: datetime
    status: EventStatus
    venue_id: str | None = None
    meeting_id: str | None = None
    racing: EventRacing = msgspec.field(default_factory=EventRacing)
    result: EventResult | None = None
    coverage: list[Coverage] | None = None
    updated_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        """Still a live card — not final, abandoned, cancelled, postponed, or unknown."""
        return self.status in LIVE_EVENT_STATUSES

    @property
    def is_final(self) -> bool:
        return self.status == "final"

    def has_status(self, status: EventStatus) -> bool:
        """Typed compare. `event.has_status("resulted")` is a type error."""
        return self.status == status


class EventPage(Page[Event]):
    items: list[Event] = []

    @property
    def open(self) -> list[Event]:
        return [event for event in self.items if event.is_open]

    @property
    def next_open(self) -> Event | None:
        return next((event for event in self.items if event.is_open), None)
