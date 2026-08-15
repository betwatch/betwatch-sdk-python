from __future__ import annotations

from datetime import datetime

from .common import Model
from .enums import CompetitorKind, Sport


class Competitor(Model):
    id: str
    sport: Sport
    kind: CompetitorKind
    name: str
    updated_at: datetime | None = None
