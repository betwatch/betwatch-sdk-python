from __future__ import annotations

from datetime import datetime

from .common import Model
from .enums import CoverageState


class Coverage(Model):
    event_id: str
    market_id: str
    source_id: str
    state: CoverageState
    complete: bool
    observed_at: datetime | None = None
