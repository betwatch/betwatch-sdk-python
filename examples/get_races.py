import logging
import os
from datetime import datetime, timedelta

import betwatch
from betwatch.types import MeetingType, RaceProjection, RacesFilter
from betwatch.types.bookmakers import Bookmaker


def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = betwatch.connect(api_key=api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(
        markets=True, flucs=True, bookmakers=[Bookmaker.SPORTSBET, Bookmaker.BLUEBET]
    )

    # define the filter for the query
    # here we can filter by date, type of meeting, and various other parameters
    races_filter = RacesFilter(
        date_from=datetime.now() - timedelta(days=7),
        date_to=datetime.now() + timedelta(days=2),
        types=[MeetingType.THOROUGHBRED],  # filter on a race type
        has_riders=["bowman", "mccoy"],  # filter on any race containing these riders
    )

    races = client.get_races(projection, races_filter)

    logging.info(f"Found {len(races)} races matching the query")
    for race in races:
        logging.info(race)


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
