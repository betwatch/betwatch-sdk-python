import os

import betwatch
from betwatch.types import RaceProjection, RaceStatus


def get_race(race_id: str):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = betwatch.connect(api_key=api_key)

    projection = RaceProjection(markets=True, flucs=True, links=True, betfair=True)

    race = client.get_race(race_id, projection)
    return race


def test_get_race():
    # Darwin R6 - 2022-12-21
    race = get_race("63a165a522ac7b5ed64336b2")
    assert race is not None
    assert race.id == "63a165a522ac7b5ed64336b2"
    assert race.status == RaceStatus.RESULTED
    assert race.meeting is not None
    assert race.meeting.track == "Darwin"
    assert race.runners and race.runners[0].betfair_id != ""
