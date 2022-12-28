import os

import pytest
from dotenv import load_dotenv

import betwatch


async def get_race_last_updated(race_id: str):
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = await betwatch.connect_async(api_key=api_key)

    return await client.get_race_last_updated_times(race_id)


@pytest.mark.asyncio
async def test_get_race():
    # Ascot R1 - 2022-12-28
    race_updates = await get_race_last_updated("63aa028d407c81ddff10b254")
    assert race_updates is not None
