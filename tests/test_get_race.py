import os
from betwatch import BetwatchClient
from dotenv import load_dotenv

from betwatch.types.race import RaceStatus


def get_race(race_id: str):
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = BetwatchClient(api_key=api_key)

    race = client.get_race(race_id)
    return race


def test_get_race():
    # Darwin R6 - 2022-12-21
    race = get_race("63a165a522ac7b5ed64336b2")
    assert race is not None
    assert race.id == "63a165a522ac7b5ed64336b2"
    assert race.status == RaceStatus.RESULTED
    assert race.meeting is not None
    assert race.meeting.track == "Darwin"
    assert race.number == 6
