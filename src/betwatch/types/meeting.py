from __future__ import annotations

from datetime import datetime

from .common import Model
from .enums import Sport
from .event import Event
from .page import Page


class Meeting(Model):
    id: str
    venue_id: str
    sport: Sport
    local_date: str
    name: str
    race_count: int = 0
    first_start_at: datetime | None = None
    last_start_at: datetime | None = None
    statuses: dict[str, int] = {}
    track_conditions: list[str] = []
    events: list[Event] = []


class MeetingPage(Page[Meeting]):
    items: list[Meeting] = []
