from __future__ import annotations

from .common import Model, Pool
from .coverage import Coverage
from .enums import SourceKind
from .page import Page


class Source(Model):
    id: str
    name: str
    kind: SourceKind
    pool: Pool | None = None
    activity: str = "unknown"
    event_id: str | None = None
    coverage: list[Coverage] = []


class SourcePage(Page[Source]):
    items: list[Source] = []
