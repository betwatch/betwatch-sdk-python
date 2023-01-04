import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import betwatch


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key)

    # get today in YYYY-MM-DD format
    today = datetime.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # get all races between today and tomorrow
    races = await client.get_races_between_dates(today, tomorrow)

    # filter only open races
    open_races = [r for r in races if r.is_open()]

    # subscribe to the 5 next open races
    for i in range(min(5, len(open_races))):
        await client.subscribe_bookmaker_updates(open_races[i].id)

    async for update in client.listen():
        print(f"Received an update for {update.race_id}")

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
    load_dotenv()
    asyncio.run(main())
