from __future__ import annotations

from datetime import datetime

from .common import Model, PriceLevel
from .enums import ExchangeMarketState, ExchangeOutcomeState, OddsState
from .page import Page
from .source import Source


class Exchange(Model):
    market_state: ExchangeMarketState
    outcome_state: ExchangeOutcomeState
    in_play: bool = False
    back: list[PriceLevel] = []
    lay: list[PriceLevel] = []
    last: float | None = None


class OddsHistoryItem(Model):
    price: float
    updated_at: datetime
    observed_at: datetime | None = None


class Odds(Model):
    id: str
    event_id: str
    market_id: str
    outcome_id: str
    source: Source
    state: OddsState
    price: float | None = None
    exchange: Exchange | None = None
    entrant_id: str | None = None
    history: list[OddsHistoryItem] | None = None
    opening_price: float | None = None
    opening_at: datetime | None = None
    observed_at: datetime | None = None
    updated_at: datetime | None = None


class OddsPage(Page[Odds]):
    items: list[Odds] = []
