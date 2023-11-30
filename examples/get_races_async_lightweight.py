"""
An example of skipping python model parsing to improve performance.
Results will be returned as raw dictionaries instead of the python models.
Betwatch helper functions will not be available on the results.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from time import time

import betwatch
from betwatch.types import MeetingType, RaceProjection, RacesFilter


async def main():
    # You can set your API here if you like to live dangerously
    # Otherwise you can set the BETWATCH_API_KEY environment variable
    api_key = None

    client = betwatch.connect_async(api_key=api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(markets=True, flucs=True)

    # define the filter for the query
    # here we can filter by date, type of meeting, and various other parameters
    races_filter = RacesFilter(
        date_from=datetime.now() - timedelta(days=3),
        date_to=datetime.now() + timedelta(days=0),
        types=[MeetingType.THOROUGHBRED],  # filter on a race type
    )

    start = time()
    races = await client.get_races(projection, races_filter)
    duration = time() - start
    print(f"Took {round(duration, 2)}s to load {len(races)} races into Python models")

    start_raw = time()
    races_raw = await client.get_races(projection, races_filter, parse_result=False)
    duration_raw = time() - start_raw
    print(
        f"Took {round(duration_raw, 2)}s to load {len(races_raw)} races into raw python dictionaries"
    )

    diff = duration - duration_raw
    print(
        f"Loading into Python dicts is {round(diff, 2)}s faster than loading into Python models ({round(diff/duration*100, 2)}% faster)"
    )


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
