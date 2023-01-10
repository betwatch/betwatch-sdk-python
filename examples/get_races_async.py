import asyncio
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

import betwatch
from betwatch.types import MeetingType, RaceProjection, RacesFilter
from betwatch.types.bookmakers import Bookmaker


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key=api_key)

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
        type=MeetingType.THOROUGHBRED,
        has_riders=["bowman", "mccoy"],
    )

    races = await client.get_races(projection, races_filter)

    print(f"Found {len(races)} races matching the query")


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    load_dotenv()
    asyncio.run(main())
