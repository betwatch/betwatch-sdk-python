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

    # get today in YYYY-MM-DD format
    today = datetime.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # don't request runner data (much faster)
    projection = RaceProjection(markets=False)

    races = client.get_races_between_dates(today, tomorrow, projection)
    if races:
        next_open = next((r for r in races if r.is_open() and r.id), None)
        if next_open and next_open.id:
            race = client.get_race(next_open.id)
            if race and race.meeting:
                print(f"Received race data for {race.meeting.track} R{race.number}")


if __name__ == "__main__":
    load_dotenv()
    main()
