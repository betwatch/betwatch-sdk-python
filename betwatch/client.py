import atexit
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Union

import backoff
import typedload
from gql import Client
from gql.transport.requests import RequestsHTTPTransport

from gql.transport.requests import log as http_logger

from betwatch.__about__ import __version__
from betwatch.queries import (
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    QUERY_GET_RACE,
    QUERY_GET_RACES,
    QUERY_GET_RACES_WITH_MARKETS,
)
from betwatch.types.bookmakers import Bookmaker
from betwatch.types.filters import RaceProjection
from betwatch.types.race import Race


class BetwatchClient:
    def __init__(self, api_key: str, transport_logging_level: int = logging.WARNING):
        self.api_key = api_key
        self._gql_transport = RequestsHTTPTransport(
            url="https://api.betwatch.com/query",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-python-{__version__}",
            },
            timeout=30,
        )
        # Create a GraphQL client using the defined transport
        self._gql_client = Client(
            transport=self._gql_transport,
        )

        http_logger.setLevel(transport_logging_level)

        # register the cleanup function to be called on exit
        atexit.register(self.__exit)

    def __exit(self):
        logging.debug("closing connection to Betwatch API")
        self.disconnect()

    def disconnect(self):
        self._gql_client.close_sync()
        self._gql_transport.close()

    def get_races_between_dates(
        self, date_from: str, date_to: str, projection=RaceProjection()
    ) -> List[Race]:
        logging.info(f"getting races between {date_from} and {date_to}")
        query = QUERY_GET_RACES_WITH_MARKETS if projection.markets else QUERY_GET_RACES
        variables = {"dateFrom": date_from, "dateTo": date_to}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("races"):
            return typedload.load(result["races"], List[Race])

        return []

    def get_race(self, race_id: str) -> Union[Race, None]:
        return self._get_race_by_id(race_id)

    def get_races_today(self) -> List[Race]:
        """Get all races for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return self.get_races_between_dates(today, tomorrow)

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    def _get_race_by_id(self, race_id: str, query=QUERY_GET_RACE) -> Union[Race, None]:
        logging.info(f"getting race (id={race_id})")
        variables = {"id": race_id}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None

    def get_race_last_updated_times(self, race_id: str) -> Dict[Bookmaker, datetime]:
        """Get the last time each bookmaker was checked for a price update.
           This does not mean that the price was updated, just that the bookmaker was checked.

        Args:
            race_id (str): race id to be checked

        Returns:
            Dict[str, datetime]: dictionary with bookmaker name as key and datetime as value
        """
        race = self._get_race_by_id(race_id, QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE)
        if not race or not race.links:
            return {}

        return {
            link.bookmaker: link.last_successful_price_update
            for link in race.links
            if link.bookmaker and link.last_successful_price_update
        }
