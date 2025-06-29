###
# Websocket subscriptions are not available on the standard API plan. Please contact us if you would like to upgrade.
###

import asyncio
import logging
import os
from datetime import datetime, timedelta

import betwatch


async def main():
    # You can set your API here if you like to live dangerously
    # Otherwise you can set the BETWATCH_API_KEY environment variable
    api_key = None

    client = betwatch.connect_async(api_key)

    # use a context handler to automatically close the connection gracefully
    async with client:
        # get today in YYYY-MM-DD format
        today = datetime.today()
        tomorrow = datetime.today() + timedelta(days=1)

        # get all races between today and tomorrow
        races = await client.get_races_between_dates(today, tomorrow)

        # filter only open races
        open_races = [r for r in races if r.is_open()]

        # subscribe to the 5 next open races
        for i in range(min(5, len(open_races))):
            await client.subscribe_bookmaker_updates(
                open_races[i].id,
                bookmakers=["Sportsbet", "Tab"],
                race_types=["Thoroughbred"],
            )
            await client.subscribe_betfair_updates(open_races[i].id)

        async for update in client.listen():
            logging.info(f"Received an update for {update.race_id}")

            # could contain a variety of information
            if update.betfair_markets:
                # has updated betfair market / prices
                print(update.betfair_markets)
            if update.bookmaker_markets:
                # has updated bookmaker market / prices
                print(update.bookmaker_markets)
            if update.race_update:
                # has updated race info (e.g. status, updated start tiem)
                print(update.race_update)


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
