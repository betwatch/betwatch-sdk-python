import pytest

import betwatch
from betwatch.types import RaceStatus


@pytest.mark.asyncio
async def test_get_race():
    # Darwin R6 - 2022-12-21
    client = betwatch.connect_async()

    race = await client.get_race("63a165a522ac7b5ed64336b2")
    assert race is not None
    assert race.id == "63a165a522ac7b5ed64336b2"
    assert race.status == RaceStatus.RESULTED
    assert race.meeting is not None
    assert race.meeting.track == "Darwin"
    assert race.number == 6

    assert (
        race.runners
        and race.runners[0]
        and race.runners[0].bookmaker_markets
        and race.runners[0].bookmaker_markets[0].id
    )

    race_from_bookmaker_market = await client.get_race_from_bookmaker_market(
        race.runners[0].bookmaker_markets[0].id
    )

    assert race_from_bookmaker_market is not None
    assert race_from_bookmaker_market.id == race.id
