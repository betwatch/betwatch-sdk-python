import os

from dotenv import load_dotenv

import betwatch


def get_races():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = betwatch.connect(api_key=api_key)

    races_from = "2022-12-21"
    races_to = "2022-12-22"

    races = client.get_races(races_from, races_to)

    return races


def test_get_races():
    # Darwin R6 - 2022-12-21
    races = get_races()
    invalid_races = [
        r
        for r in races
        if r.meeting and r.meeting.date not in ["2022-12-21", "2022-12-22"]
    ]
    assert len(invalid_races) == 0
