import logging
import os

import betwatch
from betwatch.types.updates import SelectionData


def main():
    api_key = os.getenv("BETWATCH_API_KEY")
    if not api_key:
        raise Exception("BETWATCH_API_KEY not set in .env file")

    client = betwatch.connect(api_key)

    # get a specific race (by id or by filtering a get_races call)
    race = client.get_race("64541df2ef4a7b36403781a5")
    assert race and race.runners  # make sure we received a valid response

    # given some example "ratings" that we want to update
    my_ratings = {
        1: 1.5,
        2: 2.5,
        3: 3.5,
        4: 4.5,
        5: 5.5,
    }

    # add some custom data for each selection
    # SelectionData is a typed dict of {"selection_id": str, "value": str}
    data: list[SelectionData] = []
    for runner in race.runners:
        if runner.number in my_ratings:
            # selection_id is the "id" of the selection/runner
            data.append({"selection_id": runner.id, "value": my_ratings[runner.number]})

    # Update the "Ratings" column of a race
    client.update_event_data(race.id, "Ratings", data)


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
