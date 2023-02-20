import asyncio
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

import betwatch
from betwatch.types import Bookmaker, MeetingType, RaceProjection, RacesFilter


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key=api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(
        markets=True,
        flucs=False,
        bookmakers=[Bookmaker.SPORTSBET, Bookmaker.BLUEBET, Bookmaker.NEDS],
    )

    # define the filter for the query
    # here we can filter by date, type of meeting, and various other parameters
    races_filter = RacesFilter(
        date_from=datetime.now() - timedelta(days=7),
        date_to=datetime.now() + timedelta(days=2),
        types=[MeetingType.THOROUGHBRED],
        limit=100,
        has_riders=["bowman", "mccoy"],  # filter on any race containing these riders
    )

    races = await client.get_races(projection, races_filter)

    print(f"Found {len(races)} races matching the query")

    if len(races) < 1:
        print("No races found")
        return

    if not races[0].runners:
        print("No runners found")
        return

    # we only requested sportsbet and bluebet data in the projection
    for runner in races[0].runners:
        print(f"Runner: {runner.number}. {runner.name}")
        print(f"Best Price: {runner.get_highest_bookmaker_market()}")
        print(f"Lowest Price: {runner.get_lowest_bookmaker_market()}")
        print(f"Sportsbet Price: {runner.get_bookmaker_market(Bookmaker.SPORTSBET)}")

        # get all the bookmaker markets sorted by price
        markets_sorted_by_price = runner.get_bookmaker_markets_by_price()
        print(f"Markets sorted by price: {markets_sorted_by_price}")


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
