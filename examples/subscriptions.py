###
# Websocket subscriptions are not available on the standard API plan. Please contact us if you would like to upgrade.
###

import asyncio
import logging
import os
from datetime import datetime, timedelta

import betwatch


async def main():
    api_key = os.getenv("BETWATCH_API_KEY")
    if not api_key:
        raise Exception("BETWATCH_API_KEY not set in .env file")

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
            await client.subscribe_bookmaker_updates(open_races[i].id)
            await client.subscribe_betfair_updates(open_races[i].id)

        async for update in client.listen():
            logging.info(f"Received an update for {update.race_id}")

            # could contain a variety of information
            if update.betfair_markets:
                # has updated betfair market / prices
                pass
            if update.bookmaker_markets:
                # has updated bookmaker market / prices
                pass
            if update.race_update:
                # has updated race info (e.g. status, updated start tiem)
                pass


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
