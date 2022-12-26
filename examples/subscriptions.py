import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, List

from dotenv import load_dotenv

import betwatch
from betwatch.types.markets import BookmakerMarket
from betwatch.types.race import Race


async def handle_price_updates(
    race: Race, generator: AsyncGenerator[List[BookmakerMarket], None]
):
    async for updates in generator:
        print(f"Received updated prices for {race}")


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key)

    # get today in YYYY-MM-DD format
    today = datetime.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.today() + timedelta(days=5)).strftime("%Y-%m-%d")

    async with client:
        # get all races between today and tomorrow
        races = await client.get_races(today, tomorrow)

        # filter only open races
        open_races = [r for r in races if r.is_open()]

        # subscribe to the 5 next open races
        tasks = []
        for i in range(min(100, len(open_races))):
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
