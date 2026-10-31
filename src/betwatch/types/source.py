from __future__ import annotations

from .common import Model, Pool
from .coverage import Coverage
from .enums import SourceKind
from .page import Page


class Source(Model):
    id: str
    name: str
    kind: SourceKind
    # Licensing country of a bookmaker, lower-case ISO 3166-1 alpha-2 ("au",
    # "nz", "gb"). Totes carry theirs in pool; the exchange has none. Group
    # by this, never by parsing the id: "ladbrokes-gb" is only unique.
    region: str | None = None
    pool: Pool | None = None
    activity: str = "unknown"
    event_id: str | None = None
    coverage: list[Coverage] = []


class SourcePage(Page[Source]):
    items: list[Source] = []
