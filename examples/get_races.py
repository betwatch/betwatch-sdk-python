import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

import betwatch
from betwatch.types import RaceProjection


def main():
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise Exception("API_KEY not set in .env file")

    client = betwatch.connect(api_key=api_key)

    # get dates
    today = datetime.today()
    tomorrow = datetime.today() + timedelta(days=1)

    # don't request market data (much faster)
    projection = RaceProjection(markets=False)

    races = client.get_races_between_dates(today, tomorrow, projection)
    if races:
        next_open = next((r for r in races if r.is_open() and r.id), None)
        if next_open and next_open.id:
            # get_race will always return the full data set (markets, flucs, etc)
            race = client.get_race(next_open.id)
            if race and race.meeting:
                logging.info(
                    f"Received race data for {race.meeting.track} R{race.number}"
                )


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    load_dotenv()
    main()
