from __future__ import annotations

from datetime import datetime

from .common import Model
from .enums import CoverageState, MarketKey


class Coverage(Model):
    event_id: str
    key: MarketKey
    source_id: str
    state: CoverageState
    complete: bool
    places_paid: int | None = None
    observed_at: datetime | None = None
