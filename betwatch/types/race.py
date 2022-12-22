from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from betwatch.types.markets import BetfairMarket, BookmakerMarket


class MeetingType(Enum):
    THOROUGHBRED = "Thoroughbred"
    GREYHOUND = "Greyhound"
    HARNESS = "Harness"


class RaceStatus(Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    ABANDONED = "Abandoned"
    INTERIM = "Interim"
    PAYING = "Paying"
    RESULTED = "Resulted"

    def is_closed(self) -> bool:
        return self != RaceStatus.OPEN


@dataclass
class Meeting:
    id: str
    type: MeetingType
    date: str
    track: str
    location: str
    rail_position: Optional[str] = field(
        metadata={"name": "railPosition"}, default=None
    )


@dataclass
class Runner:
    id: str
    number: int
    betfair_id: Optional[str] = field(metadata={"name": "betfairId"}, default=None)
    barrier: Optional[int] = None
    name: Optional[str] = None
    rider_name: Optional[str] = field(metadata={"name": "riderName"}, default=None)
    trainer_name: Optional[str] = field(metadata={"name": "trainerName"}, default=None)
    age: Optional[int] = None

    _scratched_time: Optional[str] = field(
        metadata={"name": "scratchedTime"}, default=None
    )

    bookmaker_markets: Optional[List[BookmakerMarket]] = field(
        metadata={"name": "bookmakerMarkets"}, default_factory=list
    )

    betfair_markets: Optional[List[BetfairMarket]] = field(
        metadata={"name": "betfairMarkets"}, default_factory=list
    )

    def is_scratched(self) -> bool:
        return self._scratched_time is not None

    def __post_init__(self):
        self.scratched_time = (
            datetime.fromisoformat(self._scratched_time)
            if self._scratched_time
            else None
        )


@dataclass
class RaceLink:
    bookmaker: Optional[str] = None
    nav_link: Optional[str] = field(metadata={"name": "navLink"}, default=None)
    _last_successful_price_update: Optional[str] = field(
        metadata={"name": "lastSuccessfulPriceUpdate"}, default=None
    )

    def __post_init__(self):
        self.last_successful_price_update = (
            datetime.fromisoformat(self._last_successful_price_update)
            if self._last_successful_price_update
            else None
        )


@dataclass
class Race:
    id: str

    status: RaceStatus

    meeting: Optional[Meeting] = None
    number: Optional[int] = None

    name: Optional[str] = None
    distance: Optional[int] = None
    classConditions: Optional[str] = field(
        metadata={"name": "classConditions"}, default=None
    )

    links: Optional[List[RaceLink]] = field(default_factory=list)
    runners: Optional[List[Runner]] = field(default_factory=list)
    results: Optional[List[List[int]]] = field(default_factory=list)

    _start_time: Optional[str] = field(metadata={"name": "startTime"}, default=None)
    _updated_at: Optional[str] = field(metadata={"name": "updatedAt"}, default=None)
    _created_at: Optional[str] = field(metadata={"name": "createdAt"}, default=None)

    def is_open(self) -> bool:
        # FIXME: should i raise an exception if status is None?
        return self.status == RaceStatus.OPEN

    def __post_init__(self):
        self.start_time = (
            datetime.fromisoformat(self._start_time) if self._start_time else None
        )
        self.updated_at = (
            datetime.fromisoformat(self._updated_at) if self._updated_at else None
        )
        self.created_at = (
            datetime.fromisoformat(self._created_at) if self._created_at else None
        )
