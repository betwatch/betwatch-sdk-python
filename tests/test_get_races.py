import betwatch


def get_races():
    client = betwatch.connect()

    races_from = "2022-12-21"
    races_to = "2022-12-22"

    races = client.get_races_between_dates(races_from, races_to)

    return races


def test_get_races():
    # Darwin R6 - 2022-12-21
    races = get_races()
    invalid_races = [
        r
        for r in races
        if r.meeting and r.meeting.date not in ["2022-12-21", "2022-12-22"]
    ]
    races_with_markets = [
        r for race in races if race.runners for r in race.runners if r.bookmaker_markets
    ]
    assert len(invalid_races) == 0
    assert len(races_with_markets) == 0
