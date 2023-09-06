import asyncio
import logging
import os

import betwatch
from betwatch.types import Bookmaker, RaceProjection


async def main():
    api_key = os.getenv("BETWATCH_API_KEY")
    if not api_key:
        raise Exception("BETWATCH_API_KEY not set in .env file")

    client = betwatch.connect_async(api_key=api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(
        markets=True,
        flucs=False,
    )

    race = await client.get_race("6412277ee60699322e4fbcdb", projection)

    if not race or not race.runners:
        logging.info("No runners found")
        return

    logging.info(f"Found race {race}")

    for runner in race.runners:
        logging.info(f"Runner: {runner.number}. {runner.name}")
        logging.info(f"Best Price: {runner.get_highest_bookmaker_market()}")
        logging.info(f"Lowest Price: {runner.get_lowest_bookmaker_market()}")
        logging.info(
            f"Sportsbet Price: {runner.get_bookmaker_market(Bookmaker.SPORTSBET)}"
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
