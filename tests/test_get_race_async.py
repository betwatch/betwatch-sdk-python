import pytest

import betwatch
from betwatch.types import RaceStatus


async def get_race(race_id: str):
    client = betwatch.connect_async()

    race = await client.get_race(race_id)
    return race


@pytest.mark.asyncio
async def test_get_race():
    # Darwin R6 - 2022-12-21
    race = await get_race("63a165a522ac7b5ed64336b2")
    assert race is not None
    assert race.id == "63a165a522ac7b5ed64336b2"
    assert race.status == RaceStatus.RESULTED
    assert race.meeting is not None
    assert race.meeting.track == "Darwin"
    assert race.number == 6
