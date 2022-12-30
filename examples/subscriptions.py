import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, List

from dotenv import load_dotenv

import betwatch
from betwatch.types import Race, RaceProjection
from betwatch.types.markets import BookmakerMarket


async def handle_price_updates(
    race: Race, generator: AsyncGenerator[List[BookmakerMarket], None]
):
    async for updates in generator:
        # find associated runner
        if not race.runners:
            continue
        for update in updates:
            runner = next(
                (
                    r
                    for r in race.runners
                    if r.bookmaker_markets
                    for m in r.bookmaker_markets
                    if m.id == update.id
                ),
                None,
            )
            if not runner:
                continue

            # print price update
            print(
                f"{race} - {runner.number}. {runner.name} - {update.fixed_win} @ {update.bookmaker}"
            )


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key)

    # get today in YYYY-MM-DD format
    today = datetime.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # request market data in order to map to request bookmaker market updates
    projection = RaceProjection(markets=True)

    # get all races between today and tomorrow
    races = await client.get_races_between_dates(today, tomorrow, projection)

    # open up a context manager to handle the connection
    # this creates a websocket connection to the Betwatch API
    async with client:
        # filter only open races
        open_races = [r for r in races if r.is_open()]

        # subscribe to the 5 next open races
        tasks = []
        for i in range(min(10, len(open_races))):
            print(f"Subscribing to price updates for {open_races[i]}...")
            tasks.append(
                asyncio.create_task(
                    handle_price_updates(
                        open_races[i], client.subscribe_price_updates(open_races[i].id)
                    )
                )
            )

        # wait for all tasks to finish (in this case this will never happen)
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
