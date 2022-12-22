import asyncio
import os
from betwatch import BetwatchAsyncClient


async def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = BetwatchAsyncClient(api_key)

    async with client:
        race1 = client.get_race("63a165a522ac7b5ed64336b2")
        race2 = client.get_race("garbage")

        result = await asyncio.gather(race1, race2)

        print([r.id for r in result if r])


if __name__ == "__main__":

    asyncio.run(main())
