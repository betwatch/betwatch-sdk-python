from __future__ import annotations

import msgspec

from .common import Model
from .enums import MarketKey, MarketPeriod, MarketState
from .page import Page


class MarketScope(Model):
    period: MarketPeriod = "full"


class SettlementParameters(Model):
    places_paid: int | None = None


class Market(Model):
    id: str
    event_id: str
    key: MarketKey
    state: MarketState
    scope: MarketScope = msgspec.field(default_factory=MarketScope)
    settlement_parameters: SettlementParameters | None = None


class MarketPage(Page[Market]):
    items: list[Market] = []
