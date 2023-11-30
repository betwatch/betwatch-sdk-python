import asyncio
import logging
import os
from datetime import datetime, timedelta

import betwatch
from betwatch.types import MeetingType, RaceProjection, RacesFilter
from betwatch.types.bookmakers import Bookmaker


async def main():
    # You can set your API here if you like to live dangerously
    # Otherwise you can set the BETWATCH_API_KEY environment variable
    api_key = None

    client = betwatch.connect_async(api_key=api_key)

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

    races = await client.get_races(projection, races_filter)

    print(f"Found {len(races)} races matching the query")


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
