from __future__ import annotations

from .common import Model, Pool
from .enums import SourceKind
from .page import Page


class Source(Model):
    id: str
    name: str
    kind: SourceKind
    pool: Pool | None = None


class SourcePage(Page[Source]):
    items: list[Source] = []
