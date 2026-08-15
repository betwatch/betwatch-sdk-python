from __future__ import annotations

from .common import Model
from .enums import Sport
from .page import Page


class Venue(Model):
    id: str
    sport: Sport
    name: str
    country: str
    timezone: str
    subdivision: str | None = None


class VenuePage(Page[Venue]):
    items: list[Venue] = []
