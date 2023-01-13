import os

from dotenv import load_dotenv

import betwatch


def get_race_last_updated(race_id: str):
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = betwatch.connect(api_key=api_key)

    return client.get_race_last_updated_times(race_id)


def test_check_last_updated_times():
    # Ascot R1 - 2022-12-28
    race_updates = get_race_last_updated("63aa028d407c81ddff10b254")
    assert race_updates is not None
