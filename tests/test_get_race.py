import betwatch
from betwatch.types import RaceProjection, RaceStatus


def test_get_race():
    client = betwatch.connect()

    projection = RaceProjection(markets=True, flucs=True, links=True, betfair=True)

    race = client.get_race("63a165a522ac7b5ed64336b2", projection)

    assert race is not None
    assert race.id == "63a165a522ac7b5ed64336b2"
    assert race.status == RaceStatus.RESULTED
    assert race.meeting is not None
    assert race.meeting.track == "Darwin"
    assert race.runners and race.runners[0].betfair_id != ""

    assert (
        race.runners
        and race.runners[0]
        and race.runners[0].bookmaker_markets
        and race.runners[0].bookmaker_markets[0].id
    )

    race_from_bookmaker_market = client.get_race_from_bookmaker_market(
        race.runners[0].bookmaker_markets[0].id
    )

    assert race_from_bookmaker_market is not None
    assert race_from_bookmaker_market.id == race.id
