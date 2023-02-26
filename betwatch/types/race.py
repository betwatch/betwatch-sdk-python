from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import dateutil.parser

from betwatch.types.markets import (
    BetfairMarket,
    Bookmaker,
    BookmakerMarket,
    MarketPriceType,
    Price,
)


@dataclass
class SubscriptionUpdate:
    race_id: str
    bookmaker_markets: List[BookmakerMarket] = field(default_factory=list)
    betfair_markets: List[BetfairMarket] = field(default_factory=list)
    race_update: Optional["RaceUpdate"] = None


class MeetingType(Enum):
    THOROUGHBRED = "Thoroughbred"
    GREYHOUND = "Greyhound"
    HARNESS = "Harness"

    def __str__(self) -> str:
        if self == MeetingType.THOROUGHBRED:
            return "R"
        if self == MeetingType.GREYHOUND:
            return "G"
        if self == MeetingType.HARNESS:
            return "H"
        return "Unknown"


class RaceStatus(Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    ABANDONED = "Abandoned"
    INTERIM = "Interim"
    PAYING = "Paying"
    RESULTED = "Resulted"


@dataclass
class Meeting:
    id: str
    type: MeetingType
    date: str
    track: str
    location: str
    # rail_position: Optional[str] = field(
    #     metadata={"name": "railPosition"}, default=None
    # )

    def __str__(self) -> str:
        return f"({self.type}) {self.track} [{self.date}]"


@dataclass
class Runner:
    id: str
    number: int
    betfair_id: str = field(metadata={"name": "betfairId"})
    barrier: int
    name: str
    rider_name: str = field(metadata={"name": "riderName"})
    trainer_name: str = field(metadata={"name": "trainerName"})
    # age: Optional[int] = None

    _scratched_time: Optional[str] = field(
        metadata={"name": "scratchedTime"}, default=None
    )

    bookmaker_markets: Optional[List[BookmakerMarket]] = field(
        metadata={"name": "bookmakerMarkets"}, default_factory=list
    )

    betfair_markets: Optional[List[BetfairMarket]] = field(
        metadata={"name": "betfairMarkets"}, default_factory=list
    )

    def __str__(self) -> str:
        return f"{self.number}. {self.name}"

    def __repr__(self) -> str:
        return f"{self.number}. {self.name}"

    def is_scratched(self) -> bool:
        return self._scratched_time is not None

    def __post_init__(self):
        self.scratched_time = (
            dateutil.parser.isoparse(self._scratched_time)
            if self._scratched_time
            else None
        )

    def get_bookmaker_market(self, bookmaker: Bookmaker) -> Optional[BookmakerMarket]:
        if not self.bookmaker_markets:
            return None
        for market in self.bookmaker_markets:
            if market.bookmaker == bookmaker:
                return market
        return None

    def get_betfair_win_market(self) -> Optional[BetfairMarket]:
        if not self.betfair_markets:
            return None
        for market in self.betfair_markets:
            if market.market_name == "win":
                return market
        return None

    def get_betfair_place_market(self) -> Optional[BetfairMarket]:
        if not self.betfair_markets:
            return None
        for market in self.betfair_markets:
            if market.market_name == "place":
                return market
        return None

    def get_bookmaker_markets_by_price(
        self,
        bookmakers: List[Bookmaker] = [bookmaker for bookmaker in Bookmaker],
        price_type: MarketPriceType = MarketPriceType.FIXED_WIN,
        max_length: Optional[int] = None,
    ) -> List[BookmakerMarket]:
        """Sorts the bookmaker markets for a runner with the given price type by price"""
        if not self.bookmaker_markets:
            return []
        best_markets: List[BookmakerMarket] = []
        best_prices: List[Price] = []
        for market in self.bookmaker_markets:
            if market.bookmaker in bookmakers:
                price = market.get_price(price_type)
                if not price or not price.price:
                    continue

                if not best_markets or not best_prices:
                    best_markets.append(market)
                    best_prices.append(price)
                    continue

                for i, best_price in enumerate(best_prices):
                    if not best_price or not best_price.price:
                        continue
                    if price.price > best_price.price:
                        best_markets.insert(i, market)
                        best_prices.insert(i, price)
                        break
                    elif i == len(best_prices) - 1:
                        best_markets.append(market)
                        best_prices.append(price)
                        break

        if max_length:
            return best_markets[:max_length]
        return best_markets

    def get_highest_bookmaker_market(
        self,
        bookmakers: List[Bookmaker] = [bookmaker for bookmaker in Bookmaker],
        market_type: MarketPriceType = MarketPriceType.FIXED_WIN,
    ) -> Optional[BookmakerMarket]:
        """Returns the best bookmaker market for a runner with the given market type"""
        best_markets = self.get_bookmaker_markets_by_price(
            bookmakers=bookmakers, price_type=market_type, max_length=1
        )
        if best_markets:
            return best_markets[0]
        return None

    def get_lowest_bookmaker_market(
        self,
        bookmakers: List[Bookmaker] = [bookmaker for bookmaker in Bookmaker],
        market_type: MarketPriceType = MarketPriceType.FIXED_WIN,
    ) -> Optional[BookmakerMarket]:
        """Returns the worst bookmaker market for a runner with the given market type"""
        best_markets = self.get_bookmaker_markets_by_price(
            bookmakers=bookmakers, price_type=market_type
        )
        if best_markets:
            return best_markets[-1]
        return None


@dataclass
class RaceLink:
    bookmaker: Optional[Bookmaker] = None
    nav_link: Optional[str] = field(metadata={"name": "navLink"}, default=None)
    _last_successful_price_update: Optional[str] = field(
        metadata={"name": "lastSuccessfulPriceUpdate"}, default=None
    )

    def __post_init__(self):
        self.last_successful_price_update = (
            dateutil.parser.isoparse(self._last_successful_price_update)
            if self._last_successful_price_update
            else None
        )


@dataclass
class RaceUpdate:
    """Only the fields that are returned in the RacesUpdated query"""

    id: str
    status: RaceStatus
    _start_time: str = field(metadata={"name": "startTime"})

    def __post_init__(self):
        self.start_time = dateutil.parser.isoparse(self._start_time)


@dataclass
class Race:
    id: str

    status: Optional[RaceStatus] = None

    runners: Optional[List[Runner]] = None

    meeting: Optional[Meeting] = None
    number: Optional[int] = None

    name: Optional[str] = None
    distance: Optional[int] = None
    classConditions: Optional[str] = field(
        metadata={"name": "classConditions"}, default=None
    )
    results: Optional[List[List[int]]] = None

    links: Optional[List[RaceLink]] = None

    _start_time: Optional[str] = field(metadata={"name": "startTime"}, default=None)

    # _updated_at: Optional[str] = field(metadata={"name": "updatedAt"}, default=None)
    # _created_at: Optional[str] = field(metadata={"name": "createdAt"}, default=None)

    def is_open(self) -> bool:
        # NOTE: Perhaps this should raise an exception if the Race object does not have a status
        return self.status == RaceStatus.OPEN

    def __post_init__(self):
        self.start_time: Optional[datetime] = (
            dateutil.parser.isoparse(self._start_time) if self._start_time else None
        )
        # self.updated_at = (
        #     dateutil.parser.isoparse(self._updated_at) if self._updated_at else None
        # )
        # self.created_at = (
        #     dateutil.parser.isoparse(self._created_at) if self._created_at else None
        # )

    def __str__(self) -> str:

        # format start_time in local timezone
        st = (
            self.start_time.astimezone().strftime(" [%d/%m/%Y %H:%M]")
            if self.start_time
            else ""
        )

        if self.meeting is None:
            return f"R{self.number} [{st}]"
        return f"({self.meeting.type}) {self.meeting.track} R{self.number}{st}"

    def get_bookmaker_link(self, bookmaker: Bookmaker) -> Optional[RaceLink]:
        """Returns the link for the given bookmaker"""
        if not self.links:
            return None
        for link in self.links:
            if link.bookmaker == bookmaker:
                return link
        return None

    def get_runners_by_price(
        self,
        market_type: MarketPriceType,
        bookmakers: List[Bookmaker] = [bookmaker for bookmaker in Bookmaker],
    ) -> List[Runner]:
        """Sorts the runners by the given market types best price"""
        if not self.runners:
            return []
        best_runners: List[Runner] = []
        best_prices: List[Price] = []
        for runner in self.runners:
            market = runner.get_highest_bookmaker_market(
                market_type=market_type, bookmakers=bookmakers
            )
            if not market:
                continue
            price = market.get_price(market_type)
            if not price or not price.price:
                continue

            if not best_runners or not best_prices:
                best_runners.append(runner)
                best_prices.append(price)
                continue

            for i, best_price in enumerate(best_prices):
                if not best_price or not best_price.price:
                    continue
                # put price at back if zero
                if (
                    price.price < best_price.price or not best_price.price
                ) and price.price:
                    best_runners.insert(i, runner)
                    best_prices.insert(i, price)
                    break
                elif i == len(best_prices) - 1:
                    best_runners.append(runner)
                    best_prices.append(price)
                    break

        return best_runners
