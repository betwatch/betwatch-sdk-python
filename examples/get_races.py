import logging
import os
from datetime import datetime, timedelta

import betwatch
from betwatch.types import MeetingType, RaceProjection, RacesFilter


def main():
    # You can set your API here if you like to live dangerously
    # Otherwise you can set the BETWATCH_API_KEY environment variable
    api_key = None

    client = betwatch.connect(api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(
        markets=True,
        place_markets=False,
        flucs=True,
        links=False,
        betfair=False,
        # bookmakers=[Bookmaker.SPORTSBET, Bookmaker.BLUEBET],
    )

    # define the filter for the query
    # here we can filter by date, type of meeting, and various other parameters
    races_filter = RacesFilter(
        limit=100,
        date_from=datetime.now() - timedelta(days=2),
        date_to=datetime.now() + timedelta(days=2),
        types=[MeetingType.THOROUGHBRED],  # filter on a race type
        locations="Australia",  # filter on a location (this could be a list of states or countries too)
    )

    races = client.get_races(projection, races_filter)

    logging.info(f"Found {len(races)} races matching the query")

    for race in races:
        logging.info(race)
        if race.runners:
            for runner in race.runners:
                print(runner)
                if not runner.bookmaker_markets:
                    print("No bookmaker markets for this runner")
                    continue
                for market in runner.bookmaker_markets:
                    print(market)
                    if market.fixed_win:
                        print(f"Fixed Win Price: {market.fixed_win.price}")
                        if market.fixed_win.flucs:
                            print(f"Total Flucs: {len(market.fixed_win.flucs)}")


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
