import asyncio

import betwatch


async def main() -> None:
    api_key = None
    async with betwatch.connect_async(api_key) as client:
        races = await client.events.list(sport="thoroughbred", country="au", limit=20)
        print(f"Found {len(races)} races")
        for race in races:
            print(race.name, race.start_at, race.status)


if __name__ == "__main__":
    asyncio.run(main())
