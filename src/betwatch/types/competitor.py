from __future__ import annotations

from datetime import datetime

import msgspec

from .common import Model, Parent
from .enums import CompetitorKind, Sport
from .page import Page
from .venue import Venue


class Competitor(Model):
    id: str
    sport: Sport
    kind: CompetitorKind
    name: str
    sex: str | None = None
    colour: str | None = None
    foal_date: datetime | None = None
    foal_date_precision: str | None = None
    sire: Parent | None = None
    dam: Parent | None = None
    updated_at: datetime | None = None


class CompetitorRun(Model):
    """A known past start, not a complete career record. None means unknown."""

    event_id: str
    entrant_id: str
    start_at: datetime
    race_number: int
    number: int
    actual_start_at: datetime | None = None
    venue: Venue | None = None
    distance_meters: int | None = None
    class_: str | None = msgspec.field(default=None, name="class")
    barrier: int | None = None
    finish: int | None = None
    field_size: int | None = None
    starting_price: float | None = None
    winning_margin: float | None = None


class CompetitorForm(Page[CompetitorRun]):
    items: list[CompetitorRun] = []
