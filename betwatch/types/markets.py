from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from typing import Optional, Union

from betwatch.types.bookmakers import Bookmaker


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


class PriceType(Enum):
    FIXED_WIN = "FIXED_WIN"
    FIXED_PLACE = "FIXED_PLACE"


@dataclass
class BookmakerMarket:
    id: Optional[str] = None
    bookmaker: Optional[Bookmaker] = None
    fixed_win: Optional[Price] = field(metadata={"name": "fixedWin"}, default=None)
    fixed_place: Optional[Price] = field(metadata={"name": "fixedPlace"}, default=None)

    def get_market(self, market_type: PriceType) -> Optional[Price]:
        if market_type == PriceType.FIXED_WIN:
            return self.fixed_win
        if market_type == PriceType.FIXED_PLACE:
            return self.fixed_place
        return None


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
