from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from betwatch.types.bookmakers import Bookmaker
from betwatch.types.race import MeetingType


def get_australian_states() -> List[str]:
    """Return a list of Australian states."""
    return [
        "ACT",
        "NSW",
        "NT",
        "QLD",
        "SA",
        "TAS",
        "VIC",
        "WA",
    ]


class RacesFilter:
    def __init__(
        self,
        limit: int = 100,
        offset: int = 0,
        types: Optional[List[Union[MeetingType, str]]] = None,
        tracks: Optional[List[str]] = None,
        locations: Optional[
            Union[
                List[str],
                Literal["Australia"],
                Literal["NZL"],
                Literal["QLD"],
                Literal["NSW"],
                Literal["VIC"],
                Literal["SA"],
                Literal["WA"],
                Literal["TAS"],
                Literal["NT"],
                Literal["ACT"],
            ]
        ] = None,
        has_bookmakers: Optional[Union[List[Bookmaker], List[str]]] = None,
        has_runners: Optional[List[str]] = None,
        has_trainers: Optional[List[str]] = None,
        has_riders: Optional[List[str]] = None,
        date_from: Optional[Union[datetime, str]] = None,
        date_to: Optional[Union[datetime, str]] = None,
    ) -> None:
        self.limit = limit
        self.offset = offset
        self.types = types if types else []
        self.tracks = tracks if tracks else []

        # if locations is a string, convert to a list
        # this is to simplify filtering for Australian races
        if locations == "Australia":
            locations = get_australian_states()
        elif isinstance(locations, list) and "Australia" in locations:
            locations.remove("Australia")
            locations.extend(get_australian_states())

        self.locations = locations if locations else []
        self.has_bookmakers = has_bookmakers if has_bookmakers else []
        self.has_runners = has_runners if has_runners else []
        self.has_trainers = has_trainers if has_trainers else []
        self.has_riders = has_riders if has_riders else []

        # parse the dates to strings
        if not date_from:
            date_from = datetime.now()
        if not date_to:
            date_to = datetime.now()
        if isinstance(date_from, datetime):
            date_from = date_from.strftime("%Y-%m-%d")
        if isinstance(date_to, datetime):
            date_to = date_to.strftime("%Y-%m-%d")

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
            "hasBookmakers": [str(bookmaker) for bookmaker in self.has_bookmakers],
            "hasRunners": self.has_runners,
            "hasTrainers": self.has_trainers,
            "hasRiders": self.has_riders,
            "dateFrom": self.date_from.strftime("%Y-%m-%d")
            if isinstance(self.date_from, datetime)
            else self.date_from,
            "dateTo": self.date_to.strftime("%Y-%m-%d")
            if isinstance(self.date_to, datetime)
            else self.date_to,
        }

    def __str__(self) -> str:
        return f"RacesFilter({('limit='+str(self.limit)+' ') if self.limit else ''}{'offset='+str(self.offset)+' ' if self.offset else ''}{'types=' + ','.join([t.value if isinstance(t, MeetingType) else t for t in self.types])} {'tracks='+str(self.tracks)} {'locations='+str(self.locations)} {'has_bookmakers='+str([str(b) for b in self.has_bookmakers])+' ' if self.has_bookmakers else ''}{'has_runners='+str(self.has_runners)+' ' if self.has_runners else ''}{'has_trainers='+str(self.has_trainers)+' ' if self.has_trainers else ''}{'has_riders='+str(self.has_riders)+' ' if self.has_riders else ''}{'date_from='+self.date_from+' ' if self.date_from else ''}{'date_to='+self.date_to if self.date_to else ''})"


class RaceProjection:
    def __init__(
        self,
        markets=False,
        place_markets=False,
        flucs=False,
        links=False,
        betfair=False,
        bookmakers: Optional[List[Union[Bookmaker, str]]] = None,
    ) -> None:
        self.markets = markets
        self.place_markets = place_markets
        self.links = links
        self.flucs = flucs
        self.betfair = betfair
        self.bookmakers = bookmakers if bookmakers else []

    def __str__(self) -> str:
        return f"RaceProjection({'markets ' if self.markets else ''}{' place_markets' if self.place_markets else ''}{' links' if self.links else ''}{' flucs' if self.flucs else ''}{' betfair' if self.betfair else ''}{' bookmakers' if self.bookmakers else ''})"
