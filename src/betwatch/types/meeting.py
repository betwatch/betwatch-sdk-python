from __future__ import annotations

from .common import Model
from .enums import Sport
from .page import Page


class Meeting(Model):
    id: str
    venue_id: str
    sport: Sport
    local_date: str
    name: str


class MeetingPage(Page[Meeting]):
    items: list[Meeting] = []
