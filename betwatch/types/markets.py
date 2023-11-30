import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

import ciso8601

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
        self.last_updated = ciso8601.parse_datetime(self._last_updated)


@dataclass
class Price:
    price: Union[float, None]
    _last_updated: str = field(metadata={"name": "lastUpdated"})

    flucs: Optional[List[Fluc]] = field(default_factory=list)

    def __repr__(self) -> str:
        # calculate fluc drop %
        if self.flucs:
            try:
                fluc_change = self.flucs[0].price - self.flucs[-1].price
                fluc_change_pct = fluc_change / self.flucs[0].price * 100
                # include ascii art arrow
                fluc_change_pct = f"{'▼' if fluc_change_pct < 0 else '▲' if fluc_change_pct != 0 else '~'} {fluc_change_pct:.2f}%"
                return f"Price({self.price}, {self.last_updated}, {len(self.flucs)} flucs, {fluc_change_pct})"
            except ZeroDivisionError:
                # handle divide by zero on empty fluc price
                pass

        return f"Price({self.price}, {self.last_updated}, {len(self.flucs) if self.flucs else 0} flucs)"

    def get_price_at_time(self, at: datetime) -> Optional[Fluc]:
        """Get the price/fluc at a certain time"""
        if not self.flucs:
            return None
        # iterate through flucs in reverse order
        for fluc in reversed(self.flucs):
            if fluc.last_updated <= at:
                return fluc
        return None

    def __str__(self) -> str:
        return self.__repr__()

    def __post_init__(self):
        self.last_updated = ciso8601.parse_datetime(self._last_updated)


class MarketPriceType(str, Enum):
    FIXED_WIN = "FIXED_WIN"
    FIXED_PLACE = "FIXED_PLACE"


@dataclass
class BookmakerMarket:
    id: str
    _bookmaker: Union[Bookmaker, str] = field(metadata={"name": "bookmaker"})
    _fixed_win: Union[None, Price, str] = field(
        metadata={"name": "fixedWin"}, default=None
    )
    _fixed_place: Union[None, Price, str] = field(
        metadata={"name": "fixedPlace"}, default=None
    )

    @property
    def fixed_win(self) -> Union[None, Price]:
        # BUG: sometimes we get a string here instead of a Price object
        # and this crashes the subscription channel
        if isinstance(self._fixed_win, str):
            self._fixed_win = None
        return self._fixed_win

    @property
    def fixed_place(self) -> Union[None, Price]:
        # BUG: sometimes we get a string here instead of a Price object
        # and this crashes the subscription channel
        if isinstance(self._fixed_place, str):
            self._fixed_place = None
        return self._fixed_place

    @property
    def bookmaker(self) -> Union[Bookmaker, str]:
        try:
            if isinstance(self._bookmaker, str):
                return Bookmaker(self._bookmaker)
            return self._bookmaker
        except ValueError:
            if isinstance(self._bookmaker, str):
                # try to find enum value by name (case insensitive)
                for bm in Bookmaker:
                    if bm.value.lower() == self._bookmaker.lower():
                        return bm
            logging.debug(f"Bookmaker has no type: {self._bookmaker}")
            return self._bookmaker

    def __repr__(self) -> str:
        return f"BookmakerMarket({str(self.bookmaker)}, FW:{self.fixed_win}, FP:{self.fixed_place})"

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
            ciso8601.parse_datetime(self._last_updated) if self._last_updated else None
        )


class BetfairSide(str, Enum):
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
