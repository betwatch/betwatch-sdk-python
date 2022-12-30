import os

import pytest
from dotenv import load_dotenv

import betwatch


async def get_races():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key=api_key)

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
