from datetime import datetime
from typing import Any, Dict, List, Union

from betwatch.types.bookmakers import Bookmaker
from betwatch.types.race import MeetingType


class RacesFilter:
    def __init__(
        self,
        limit: int = 100,
        offset: int = 0,
        types: List[Union[MeetingType, str]] = [],
        tracks: List[str] = [],
        locations: List[str] = [],
        has_bookmakers: List[Bookmaker] = [],
        has_runners: List[str] = [],
        has_trainers: List[str] = [],
        has_riders: List[str] = [],
        date_from: datetime = datetime.now(),
        date_to: datetime = datetime.now(),
    ) -> None:
        self.limit = limit
        self.offset = offset
        self.types = types
        self.tracks = tracks
        self.locations = locations
        self.has_bookmakers = has_bookmakers
        self.has_runners = has_runners
        self.has_trainers = has_trainers
        self.has_riders = has_riders
        self.date_from = date_from
        self.date_to = date_to

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict."""
        return {
            "limit": self.limit,
            "offset": self.offset,
            "types": [t.value if isinstance(t, MeetingType) else t for t in self.types],
            "tracks": self.tracks,
            "locations": self.locations,
            "hasBookmakers": [bookmaker.value for bookmaker in self.has_bookmakers],
            "hasRunners": self.has_runners,
            "hasTrainers": self.has_trainers,
            "hasRiders": self.has_riders,
            "dateFrom": self.date_from.strftime("%Y-%m-%d"),
            "dateTo": self.date_to.strftime("%Y-%m-%d"),
        }

    def __str__(self) -> str:
        return f"RacesFilter({('limit='+str(self.limit)+' ') if self.limit else ''}{'offset='+str(self.offset)+' ' if self.offset else ''}{'types=' + ','.join([t.value if isinstance(t, MeetingType) else t for t in self.types])} {'tracks='+str(self.tracks)} {'locations='+str(self.locations)} {'has_bookmakers='+str([b.value for b in self.has_bookmakers])+' ' if self.has_bookmakers else ''}{'has_runners='+str(self.has_runners)+' ' if self.has_runners else ''}{'has_trainers='+str(self.has_trainers)+' ' if self.has_trainers else ''}{'has_riders='+str(self.has_riders)+' ' if self.has_riders else ''}{'date_from='+self.date_from.strftime('%Y-%m-%d')+' ' if self.date_from else ''}{'date_to='+self.date_to.strftime('%Y-%m-%d') if self.date_to else ''})"


class RaceProjection:
    def __init__(
        self,
        markets=False,
        place_markets=False,
        flucs=False,
        links=False,
        betfair=False,
        bookmakers: List[Bookmaker] = [],
    ) -> None:
        self.markets = markets
        self.place_markets = place_markets
        self.links = links
        self.flucs = flucs
        self.betfair = betfair
        self.bookmakers = bookmakers

    def __str__(self) -> str:
        return f"RaceProjection({'markets ' if self.markets else ''}{' place_markets' if self.place_markets else ''}{' links' if self.links else ''}{' flucs' if self.flucs else ''}{' betfair' if self.betfair else ''}{' bookmakers' if self.bookmakers else ''})"
