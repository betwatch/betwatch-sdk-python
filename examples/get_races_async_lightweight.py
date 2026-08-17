"""Same list as get_races_async, dumped to dicts for pandas."""

import asyncio

import betwatch


async def main() -> None:
    api_key = None
    async with betwatch.AsyncBetwatch(api_key) as client:
        races = await client.events.list(sport="thoroughbred", country="au", limit=50)
        rows = races.to_records()
        print(f"{len(races)} races as models, {len(rows)} dict rows")
        print(rows[0]["name"] if rows else "none")


if __name__ == "__main__":
    asyncio.run(main())
