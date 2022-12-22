import asyncio
from datetime import datetime, timedelta
import os
from typing import AsyncGenerator, List
from betwatch import BetwatchAsyncClient
from betwatch.types.markets import BookmakerMarket
from dotenv import load_dotenv


async def handle_price_updates(generator: AsyncGenerator[List[BookmakerMarket], None]):
    async for updates in generator:
        print(updates)


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = BetwatchAsyncClient(api_key)

    # get today in YYYY-MM-DD format
    today = datetime.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    async with client:
        # get all races between today and tomorrow
        races = await client.get_races(today, tomorrow)

        # filter only open races
        open_races = [r for r in races if r.is_open()]

        # subscribe to the 10 next open races
        tasks = []
        for i in range(10):
            tasks.append(
                asyncio.create_task(
                    handle_price_updates(
                        client.subscribe_price_updates(open_races[i].id)
                    )
                )
            )

        # wait for all tasks to finish (in this case this will never happen)
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
