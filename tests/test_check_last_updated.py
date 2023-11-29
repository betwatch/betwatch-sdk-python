import betwatch


def get_race_last_updated(race_id: str):
    client = betwatch.connect()

    return client.get_race_last_updated_times(race_id)


def test_check_last_updated_times():
    # Ascot R1 - 2022-12-28
    race_updates = get_race_last_updated("63aa028d407c81ddff10b254")
    assert race_updates is not None
