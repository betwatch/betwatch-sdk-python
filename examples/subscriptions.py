"""Live prices for the next few open races. Ctrl+C to stop."""

import asyncio

import betwatch
from betwatch import OddsFrame


async def main() -> None:
    api_key = None
    async with betwatch.connect_async(api_key) as client:
        races = await client.events.list(sport="thoroughbred", country="au", limit=20)
        ids = [race.id for race in races.open][:5] or [races[0].id]
        async with client.stream(event=ids, snapshot="full") as stream:
            async for frame in stream:
                if isinstance(frame, OddsFrame):
                    print(frame.data.source.id, frame.data.price)


if __name__ == "__main__":
    asyncio.run(main())
