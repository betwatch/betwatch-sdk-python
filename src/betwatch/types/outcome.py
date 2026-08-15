from __future__ import annotations

from .common import Model
from .enums import OutcomeKey, OutcomeState
from .page import Page


class Outcome(Model):
    id: str
    market_id: str
    key: OutcomeKey
    name: str
    state: OutcomeState
    entrant_id: str | None = None


class OutcomePage(Page[Outcome]):
    items: list[Outcome] = []
