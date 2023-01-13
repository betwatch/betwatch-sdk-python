import atexit
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Union

import backoff
import typedload
from gql import Client
from gql.transport.exceptions import TransportQueryError
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.requests import log as http_logger
from graphql import DocumentNode

from betwatch.__about__ import __version__
from betwatch.queries import (
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    query_get_race,
    query_get_races,
)
from betwatch.types import Bookmaker, Race, RaceProjection
from betwatch.types.filters import RacesFilter


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
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection=RaceProjection(),
        filter=RacesFilter(),
    ) -> List[Race]:
        """Get a list of races in between two dates.

        Args:
            date_from (Union[str, datetime]): Date to start from (inclusive)
            date_to (Union[str, datetime]): Date to end at (inclusive   )
            projection (_type_, optional): The fields to return. Defaults to RaceProjection().
            filter (_type_, optional): Filter the results. Defaults to RacesFilter().

        Returns:
            List[Race]: List of races that match the criteria
        """
        if isinstance(date_from, datetime):
            date_from = date_from.strftime("%Y-%m-%d")
        if isinstance(date_to, datetime):
            date_to = date_to.strftime("%Y-%m-%d")

        # prefer the date_from and date_to passed into the function
        if filter.date_from and filter.date_from != date_from:
            logging.warning(
                f"Overriding date_from in filter ({filter.date_from} with {date_from})"
            )
            filter.date_from = datetime.strptime(date_from, "%Y-%m-%d")
        if filter.date_to and filter.date_to != date_to:
            logging.warning(
                f"Overriding date_to in filter ({filter.date_to} with {date_to})"
            )
            filter.date_to = datetime.strptime(date_to, "%Y-%m-%d")
        return self.get_races(projection, filter)

    def get_races(
        self,
        projection=RaceProjection(),
        filter=RacesFilter(),
    ) -> List[Race]:
        try:
            logging.info(
                f"Getting races with projection {projection} and filter {filter}"
            )

            done = False
            races: List[Race] = []
            # iterate until no more races are found
            while not done:

                query = query_get_races(projection)

                variables = filter.to_dict()

                result = self._gql_client.execute(query, variable_values=variables)

                if result.get("races"):
                    logging.debug(
                        f"Received {len(result['races'])} races - attempting to get more"
                    )
                    races.extend(typedload.load(result["races"], List[Race]))

                    # change the offset to the next page
                    filter.offset += filter.limit
                else:
                    filter.offset = 0
                    logging.debug("No more races found")
                    done = True

            return races
        # except (ClientError, HTTPClientError, HTTPServerError) as e:
        #     logging.warning(f"Error reaching Betwatch API: {e}")
        #     raise e
        except TransportQueryError as e:
            if e.errors:
                for error in e.errors:
                    msg = error.get("message")
                    if msg:
                        # sometimes we can provide better feedback
                        if "limit argument" in msg:
                            # adjust the limit and try again

                            filter.limit = int(
                                msg.split("limit argument less than")[1].strip()
                            )
                            logging.info(
                                f"Cannot query more than {filter.limit} - adjusting limit to {filter.limit} and trying again"
                            )
                            return self.get_races(projection, filter)
                        else:
                            logging.error(f"{error}")
                    else:
                        logging.error(f"{error}")
            else:
                logging.error(f"Error querying Betwatch API: {e}")
            return []

    def get_race(
        self, race_id: str, projection=RaceProjection(markets=True)
    ) -> Union[Race, None]:
        query = query_get_race(projection)
        return self._get_race_by_id(race_id, query)

    def get_races_today(self, projection=RaceProjection()) -> List[Race]:
        """Get all races for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=0)).strftime("%Y-%m-%d")
        return self.get_races_between_dates(today, tomorrow, projection)

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    def _get_race_by_id(self, race_id: str, query: DocumentNode) -> Union[Race, None]:
        logging.info(f"Getting race (id={race_id})")
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
