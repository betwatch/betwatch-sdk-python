import pytest

import betwatch


async def get_races():
    client = betwatch.connect_async()

    races_from = "2022-12-21"
    races_to = "2022-12-22"

    races = await client.get_races_between_dates(races_from, races_to)

    return races


@pytest.mark.asyncio
async def test_get_races():
    # Darwin R6 - 2022-12-21
    races = await get_races()
    invalid_races = [
        r
        for r in races
        if r.meeting and r.meeting.date not in ["2022-12-21", "2022-12-22"]
    ]
    assert len(invalid_races) == 0
