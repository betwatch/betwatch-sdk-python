import contextlib
import dataclasses
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Literal, Optional

import ciso8601

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
    bookmaker_markets: list[BookmakerMarket] = field(default_factory=list)
    betfair_markets: list[BetfairMarket] = field(default_factory=list)
    race_update: Optional["RaceUpdate"] = None


class MeetingType(str, Enum):
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


class RaceStatus(str, Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    ABANDONED = "Abandoned"
    INTERIM = "Interim"
    PAYING = "Paying"
    RESULTED = "Resulted"


@dataclass
class Meeting:
    id: str
    _type: MeetingType | str = field(metadata={"name": "type"})
    date: str
    track: str
    location: str
    # rail_position: Optional[str] = field(
    #     metadata={"name": "railPosition"}, default=None
    # )

    @property
    def type(self) -> MeetingType | str:
        try:
            if isinstance(self._type, str):
                return MeetingType(self._type)
            return self._type
        except ValueError:
            if isinstance(self._type, str):
                # try to find enum value by name (case insensitive)
                for mt in MeetingType:
                    if mt.value.lower() == self._type.lower():
                        return mt
            # Return the string if meeting type is unknown
            return self._type

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
    emergency: bool
    # age: Optional[int] = None

    _scratched_time: str | None = field(metadata={"name": "scratchedTime"}, default=None)

    bookmaker_markets: list[BookmakerMarket] | None = field(metadata={"name": "bookmakerMarkets"}, default_factory=list)

    betfair_markets: list[BetfairMarket] | None = field(metadata={"name": "betfairMarkets"}, default_factory=list)

    def __str__(self) -> str:
        return f"{self.number}. {self.name}"

    def __repr__(self) -> str:
        return f"{self.number}. {self.name}"

    def is_scratched(self) -> bool:
        return self._scratched_time is not None

    def __post_init__(self):
        self.scratched_time = ciso8601.parse_datetime(self._scratched_time) if self._scratched_time else None

    def get_bookmaker_market(self, bookmaker: Bookmaker | str) -> BookmakerMarket | None:
        # try to get bookmaker if passed as string
        if isinstance(bookmaker, str):
            with contextlib.suppress(ValueError):
                bookmaker = Bookmaker(bookmaker)

        if not self.bookmaker_markets:
            return None
        for market in self.bookmaker_markets:
            if market.bookmaker == bookmaker:
                return market
        return None

    def get_betfair_win_market(self) -> BetfairMarket | None:
        if not self.betfair_markets:
            return None
        for market in self.betfair_markets:
            if market.market_name == "win":
                return market
        return None

    def get_betfair_place_market(self) -> BetfairMarket | None:
        if not self.betfair_markets:
            return None
        for market in self.betfair_markets:
            if market.market_name == "place":
                return market
        return None

    def get_bookmaker_markets_by_price(
        self,
        bookmakers: list[Bookmaker] | None = None,
        price_type: MarketPriceType = MarketPriceType.FIXED_WIN,
        max_length: int | None = None,
    ) -> list[BookmakerMarket]:
        """Sorts the bookmaker markets for a runner with the given price type by price"""
        # handle defaults
        if not bookmakers:
            bookmakers = list(Bookmaker)

        if not self.bookmaker_markets:
            return []
        best_markets: list[BookmakerMarket] = []
        best_prices: list[Price] = []
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
        bookmakers: list[Bookmaker] | None = None,
        market_type: MarketPriceType = MarketPriceType.FIXED_WIN,
    ) -> BookmakerMarket | None:
        """Returns the best bookmaker market for a runner with the given market type"""
        # handle defaults
        if not bookmakers:
            bookmakers = list(Bookmaker)

        best_markets = self.get_bookmaker_markets_by_price(bookmakers=bookmakers, price_type=market_type, max_length=1)
        if best_markets:
            return best_markets[0]
        return None

    def get_lowest_bookmaker_market(
        self,
        bookmakers: list[Bookmaker] | None = None,
        market_type: Literal["FIXED_WIN", "FIXED_PLACE"] | MarketPriceType = MarketPriceType.FIXED_WIN,
    ) -> BookmakerMarket | None:
        """Returns the worst bookmaker market for a runner with the given market type"""
        # handle defaults
        if not bookmakers:
            bookmakers = list(Bookmaker)

        # parse market type
        if isinstance(market_type, str):
            try:
                market_type = MarketPriceType(market_type)
            except ValueError:
                # If market type is unknown, default to FIXED_WIN
                market_type = MarketPriceType.FIXED_WIN

        best_markets = self.get_bookmaker_markets_by_price(bookmakers=bookmakers, price_type=market_type)
        if best_markets:
            return best_markets[-1]
        return None


@dataclass
class RaceLink:
    _bookmaker: Bookmaker | str = field(metadata={"name": "bookmaker"})
    nav_link: str | None = field(metadata={"name": "navLink"}, default=None)
    fixed_win_link: str | None = field(metadata={"name": "fixedWin"}, default=None)
    _last_successful_price_update: str | None = field(metadata={"name": "lastSuccessfulPriceUpdate"}, default=None)

    def __post_init__(self):
        self.last_successful_price_update = (
            ciso8601.parse_datetime(self._last_successful_price_update) if self._last_successful_price_update else None
        )

    @property
    def bookmaker(self) -> Bookmaker | str:
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
            # Return the string if bookmaker is unknown instead of raising
            return self._bookmaker


@dataclass
class RaceUpdate:
    """Only the fields that are returned in the RacesUpdated query"""

    id: str
    _status: RaceStatus | str = field(metadata={"name": "status"})
    _start_time: str = field(metadata={"name": "startTime"})

    @property
    def status(self) -> RaceStatus | str:
        try:
            if isinstance(self._status, str):
                return RaceStatus(self._status)
            return self._status
        except ValueError:
            if isinstance(self._status, str):
                # try to find enum value by name (case insensitive)
                for rs in RaceStatus:
                    if rs.value.lower() == self._status.lower():
                        return rs
            # Return the string if race status is unknown
            return self._status

    def __post_init__(self):
        self.start_time = ciso8601.parse_datetime(self._start_time)


class EnhancedJSONEncoder(json.JSONEncoder):
    # Create a custom encoder to handle nested dataclasses
    # and convert them to dicts. Also handles datetime objects
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        elif isinstance(o, timedelta):
            return (datetime.min + o).time().isoformat()
        elif isinstance(o, Enum):
            return o.value
        return super().default(o)


@dataclass
class Race:
    id: str

    _status: RaceStatus | str | None = field(metadata={"name": "status"}, default=None)

    runners: list[Runner] | None = None

    meeting: Meeting | None = None
    number: int | None = None

    name: str | None = None
    distance: int | None = None
    class_conditions: str | None = field(metadata={"name": "classConditions"}, default=None)
    track_condition: str | None = field(metadata={"name": "trackCondition"}, default=None)
    results: list[list[int]] | None = None

    links: list[RaceLink] | None = None

    _start_time: str | None = field(metadata={"name": "startTime"}, default=None)
    _actual_start_time: str | None = field(metadata={"name": "actualStartTime"}, default=None)

    @property
    def status(self) -> RaceStatus | str | None:
        if self._status is None:
            return None
        try:
            if isinstance(self._status, str):
                return RaceStatus(self._status)
            return self._status
        except ValueError:
            if isinstance(self._status, str):
                # try to find enum value by name (case insensitive)
                for rs in RaceStatus:
                    if rs.value.lower() == self._status.lower():
                        return rs
            # Return the string if race status is unknown
            return self._status

    def is_open(self) -> bool:
        # NOTE: Perhaps this should raise an exception if the Race object does not have a status
        return self.status == RaceStatus.OPEN

    def __post_init__(self):
        self.start_time: datetime | None = ciso8601.parse_datetime(self._start_time) if self._start_time else None
        self.actual_start_time: datetime | None = (
            ciso8601.parse_datetime(self._actual_start_time) if self._actual_start_time else None
        )

    def __str__(self) -> str:
        # format start_time in local timezone
        st = self.start_time.astimezone().strftime(" [%d/%m/%Y %H:%M]") if self.start_time else ""

        if self.meeting is None:
            return f"R{self.number} [{st}]"
        return f"({self.meeting.type}) {self.meeting.track} R{self.number}{st}"

    def __repr__(self) -> str:
        return str(self)

    def get_bookmaker_link(self, bookmaker: Bookmaker | str) -> RaceLink | None:
        """Returns the link for the given bookmaker"""
        # parse bookmaker if string
        if isinstance(bookmaker, str):
            with contextlib.suppress(ValueError):
                bookmaker = Bookmaker(bookmaker)

        if not self.links:
            return None
        for link in self.links:
            if link.bookmaker == bookmaker:
                return link
        return None

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self, cls=EnhancedJSONEncoder))

    def get_runners_by_price(
        self,
        market_type: MarketPriceType,
        bookmakers: list[Bookmaker] | None = None,
    ) -> list[Runner]:
        """Sorts the runners by the given market types best price"""
        # handle defaults
        if not bookmakers:
            bookmakers = list(Bookmaker)
        if not self.runners:
            return []
        best_runners: list[Runner] = []
        best_prices: list[Price] = []
        for runner in self.runners:
            market = runner.get_highest_bookmaker_market(market_type=market_type, bookmakers=bookmakers)
            if not market:
                continue
            price = market.get_price(market_type)
            if not price or not price.price or price.price <= 1.01:
                continue

            if runner.scratched_time:
                continue

            if not best_runners or not best_prices:
                best_runners.append(runner)
                best_prices.append(price)
                continue

            for i, best_price in enumerate(best_prices):
                if not best_price or not best_price.price:
                    continue
                # put price at back if zero
                if (price.price < best_price.price or not best_price.price) and price.price > 1.01:
                    best_runners.insert(i, runner)
                    best_prices.insert(i, price)
                    break
                elif i == len(best_prices) - 1:
                    best_runners.append(runner)
                    best_prices.append(price)
                    break

        return best_runners
