from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

import dateutil.parser

from betwatch.types import Bookmaker


@dataclass
class Fluc:
    price: float
    _last_updated: str = field(metadata={"name": "lastUpdated"})

    def __repr__(self) -> str:
        return f"Fluc({self.price}, {self.last_updated})"

    def __str__(self) -> str:
        return self.__repr__()

    def __post_init__(self):
        self.last_updated = dateutil.parser.isoparse(self._last_updated)


@dataclass
class Price:
    price: float
    _last_updated: str = field(metadata={"name": "lastUpdated"})

    flucs: Optional[List[Fluc]] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Price({self.price}, {self.last_updated}, {len(self.flucs) if self.flucs else 0} flucs)"

    def __str__(self) -> str:
        return self.__repr__()

    def __post_init__(self):
        self.last_updated = dateutil.parser.isoparse(self._last_updated)


class MarketPriceType(Enum):
    FIXED_WIN = "FIXED_WIN"
    FIXED_PLACE = "FIXED_PLACE"


@dataclass
class BookmakerMarket:
    id: str
    bookmaker: Bookmaker
    fixed_win: Price = field(metadata={"name": "fixedWin"})
    fixed_place: Optional[Price] = field(metadata={"name": "fixedPlace"}, default=None)

    def __repr__(self) -> str:
        return f"BookmakerMarket({self.bookmaker.value}, FW:{self.fixed_win}, FP:{self.fixed_place})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_price(self, market_type: MarketPriceType) -> Optional[Price]:
        if market_type == MarketPriceType.FIXED_WIN:
            return self.fixed_win
        if market_type == MarketPriceType.FIXED_PLACE:
            return self.fixed_place
        return None


@dataclass
class BetfairTick:
    price: float
    size: float
    _last_updated: Optional[str] = field(metadata={"name": "lastUpdated"}, default=None)

    def __post_init__(self):
        self.last_updated = (
            dateutil.parser.isoparse(self._last_updated) if self._last_updated else None
        )


class BetfairSide(Enum):
    BACK = "BACK"
    LAY = "LAY"


@dataclass
class BetfairMarket:
    id: str
    total_matched: float = field(metadata={"name": "totalMatched"})
    market_total_matched: float = field(metadata={"name": "marketTotalMatched"})
    starting_price: float = field(metadata={"name": "sp"})

    back: Optional[List[BetfairTick]] = field(default_factory=list)
    lay: Optional[List[BetfairTick]] = field(default_factory=list)

    market_name: Optional[str] = field(metadata={"name": "marketName"}, default=None)
    last_price_traded: Optional[float] = field(
        metadata={"name": "lastPriceTraded"}, default=None
    )
    market_id: Optional[str] = field(metadata={"name": "marketId"}, default=None)

    @property
    def sp(self) -> Union[float, None]:
        return self.starting_price
