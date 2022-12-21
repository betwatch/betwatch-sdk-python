import asyncio
import os
from betwatch import BetwatchAsyncClient
from dotenv import load_dotenv


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = BetwatchAsyncClient(api_key=api_key)
    races = await client.get_races("2022-12-21", "2022-12-22")
    if races:
        next_open = next((r for r in races if r.is_open() and r.id), None)
        if next_open and next_open.id:
            race = await client.get_race(next_open.id)
            if race:
                print(f"Received race data for {race.meeting.track} R{race.number}")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
