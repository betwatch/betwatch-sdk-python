import logging
import os
from datetime import timedelta

from betwatch.client import BetwatchClient
from betwatch.types import Bookmaker, RaceProjection


def main():
    api_key = os.getenv("BETWATCH_API_KEY")
    if not api_key:
        raise Exception("BETWATCH_API_KEY not set in .env file")

    # client = betwatch.connect(api_key=api_key)
    client = BetwatchClient(api_key=api_key)

    # define the projection of the returned data
    # we can filter out for certain bookmakers as well as define whether we want market data or flucs
    projection = RaceProjection(
        markets=True,
        flucs=True,
        # bookmakers=[Bookmaker.SPORTSBET, Bookmaker.TAB],
    )

    races = client.get_races_today(projection)
    race = next(r for r in races if r.is_open())

    if not race or not race.runners:
        logging.info("No runners found")
        return

    logging.info(f"Found race {race}")

    for runner in race.runners:
        if not runner or runner.is_scratched():
            continue

        logging.info(f"Runner: {runner.number}. {runner.name}")
        logging.info(f"Best Price: {runner.get_highest_bookmaker_market()}")
        logging.info(
            f"Lowest Price: {runner.get_lowest_bookmaker_market(market_type='FIXED_PLACE')}"
        )
        logging.info(
            f"Sportsbet Price: {runner.get_bookmaker_market(Bookmaker.SPORTSBET)}"
        )

        # check we have valid responses
        # in a real world scenario, we should check these before using them
        assert runner.bookmaker_markets is not None
        assert race.start_time is not None

        # runner.bookmaker_markets is a list of BookmakerMarket objects
        # we can iterate over these to get the bookmaker and market data
        for bookmaker_market in runner.bookmaker_markets:
            assert bookmaker_market.fixed_win is not None

            logging.info(
                f"{bookmaker_market.bookmaker}: {bookmaker_market.fixed_win.price}"
            )

            # ... or we can get a price/fluc at some point of time
            at = race.start_time - timedelta(minutes=10)  # 10 minutes before jump
            fluc = bookmaker_market.fixed_win.get_price_at_time(at)
            if fluc:
                logging.info(
                    f"{bookmaker_market.bookmaker} price at {at} was: {fluc.price}"
                )


if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        handlers=[logging.StreamHandler()],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
