from datetime import datetime, timedelta
from time import time

import pytest

import betwatch


async def subscribe_races():
    client = betwatch.connect_async()

    today = datetime.today()
    tomorrow = datetime.today() + timedelta(days=1)

    # get all races between today and tomorrow
    races = await client.get_races_between_dates(today, tomorrow)

    # filter only open races
    open_races = [r for r in races if r.is_open()]

    # subscribe to the 5 next open races
    for i in range(min(5, len(open_races))):
        await client.subscribe_bookmaker_updates(open_races[i].id)
        await client.subscribe_betfair_updates(open_races[i].id)

    # check we receive both types of updates
    betfair_ok = False
    bookmaker_ok = False

    start_time = time()

    async for update in client.listen():
        # could contain a variety of information
        if update.betfair_markets:
            # has updated betfair market / prices
            betfair_ok = True
        if update.bookmaker_markets:
            # has updated bookmaker market / prices
            bookmaker_ok = True

        if betfair_ok and bookmaker_ok:
            break

        # timeout after 10 seconds
        if time() - start_time > 60:
            break

    assert betfair_ok
    assert bookmaker_ok
    await client.disconnect()


@pytest.mark.asyncio
async def test_subscribe_races():
    await subscribe_races()
