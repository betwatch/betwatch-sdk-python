from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Union


@dataclass
class Fluc:
    price: Optional[float] = None
    _last_updated: Optional[str] = field(metadata={"name": "lastUpdated"}, default=None)

    def __post_init__(self):
        self.last_updated = (
            datetime.fromisoformat(self._last_updated) if self._last_updated else None
        )


@dataclass
class Price:
    price: Optional[float] = None
    flucs: Optional[list[Fluc]] = field(default_factory=list)
    _last_updated: Optional[str] = field(metadata={"name": "lastUpdated"}, default=None)

    def __post_init__(self):
        self.last_updated = (
            datetime.fromisoformat(self._last_updated) if self._last_updated else None
        )


@dataclass
class BookmakerMarket:
    id: Optional[str] = None
    bookmaker: Optional[str] = None
    fixed_win: Optional[Price] = field(metadata={"name": "fixedWin"}, default=None)
    fixed_place: Optional[Price] = field(metadata={"name": "fixedPlace"}, default=None)


@dataclass
class BetfairTick:
    price: Optional[float] = None
    size: Optional[float] = None
    _last_updated: Optional[str] = field(metadata={"name": "lastUpdated"}, default=None)

    def __post_init__(self):
        self.last_updated = (
            datetime.fromisoformat(self._last_updated) if self._last_updated else None
        )


@dataclass
class BetfairMarket:
    id: Optional[str] = None
    market_id: Optional[str] = field(metadata={"name": "marketId"}, default=None)
    market_name: Optional[str] = field(metadata={"name": "marketName"}, default=None)
    total_matched: Optional[float] = field(
        metadata={"name": "totalMatched"}, default=None
    )
    market_total_matched: Optional[float] = field(
        metadata={"name": "marketTotalMatched"}, default=None
    )
    last_price_traded: Optional[float] = field(
        metadata={"name": "lastPriceTraded"}, default=None
    )
    starting_price: Optional[float] = field(metadata={"name": "sp"}, default=None)

    back: Optional[list[BetfairTick]] = field(default_factory=list)
    lay: Optional[list[BetfairTick]] = field(default_factory=list)

    @property
    def sp(self) -> Union[float, None]:
        return self.starting_price
