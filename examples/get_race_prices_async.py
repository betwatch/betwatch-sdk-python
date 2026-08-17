import asyncio

import betwatch


async def main() -> None:
    api_key = None
    async with betwatch.AsyncBetwatch(api_key) as client:
        races = await client.events.list(sport="thoroughbred", country="au", limit=20)
        race = races.next_open or (races[0] if races else None)
        if race is None:
            raise SystemExit("No races found in the current event window")
        card = await client.events.snapshot(race.id)
        print(card.event.name)
        for runner in card.entrants:
            print(
                runner.number,
                runner.name,
                "best",
                card.best_price(runner),
                "sportsbet",
                card.price(runner, "sportsbet"),
            )


if __name__ == "__main__":
    asyncio.run(main())
