import atexit
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional, Union, overload

import backoff
import typedload
from gql import Client
from gql.transport.exceptions import TransportQueryError
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.requests import log as http_logger
from graphql import DocumentNode

from betwatch.__about__ import __version__
from betwatch.exceptions import APIKeyNotSetError
from betwatch.queries import (
    MUTATION_UPDATE_USER_EVENT_DATA,
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    query_get_race,
    query_get_races,
)
from betwatch.types import Bookmaker, Race, RaceProjection
from betwatch.types.filters import RacesFilter
from betwatch.types.updates import SelectionData

log = logging.getLogger(__name__)


class BetwatchClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        transport_logging_level: int = logging.WARNING,
        host="api.betwatch.com",
        request_timeout=60,
    ):
        if not api_key:
            api_key = os.environ.get("BETWATCH_API_KEY")
        if not api_key:
            raise APIKeyNotSetError()

        self.api_key = api_key
        self._gql_transport = RequestsHTTPTransport(
            url=f"https://{host}/query",
            headers={
                "X-Api-Key": self.api_key,
                "User-Agent": f"betwatch-python-{__version__}",
            },
            timeout=request_timeout,
        )
        # Create a GraphQL client using the defined transport
        self._gql_client = Client(
            transport=self._gql_transport,
        )

        http_logger.setLevel(transport_logging_level)

        # register the cleanup function to be called on exit
        atexit.register(self.__exit)

    def __exit(self):
        log.debug("closing connection to Betwatch API")
        self.disconnect()

    def disconnect(self):
        self._gql_client.close_sync()
        self._gql_transport.close()

    @overload
    def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[True] = True,
    ) -> List[Race]:
        ...

    @overload
    def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[False] = False,
    ) -> List[Dict]:
        ...

    def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: bool = True,
    ) -> Union[List[Race], List[Dict]]:
        """Get a list of races in between two dates.

        Args:
            date_from (Union[str, datetime]): Date to start from (inclusive)
            date_to (Union[str, datetime]): Date to end at (inclusive)
            projection (_type_, optional): The fields to return. Defaults to RaceProjection().
            filter (_type_, optional): Filter the results. Defaults to RacesFilter().

        Returns:
            Union[List[Race], List[Dict]]: List of races that match the criteria
        """
        # handle defaults
        if not projection:
            projection = RaceProjection()
        if not filter:
            filter = RacesFilter()

        if isinstance(date_from, datetime):
            date_from = date_from.strftime("%Y-%m-%d")
        if isinstance(date_to, datetime):
            date_to = date_to.strftime("%Y-%m-%d")

        # prefer the date_from and date_to passed into the function
        if filter.date_from and filter.date_from != date_from:
            log.debug(
                f"Overriding date_from in filter ({filter.date_from} with {date_from})"
            )
            filter.date_from = date_from
        if filter.date_to and filter.date_to != date_to:
            log.debug(f"Overriding date_to in filter ({filter.date_to} with {date_to})")
            filter.date_to = date_to
        return self.get_races(projection, filter)

    @overload
    def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[True] = True,
    ) -> List[Race]:
        ...

    @overload
    def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[False] = False,
    ) -> List[Dict]:
        ...

    def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: bool = True,
    ) -> Union[List[Race], List[Dict]]:
        # handle defaults
        if not projection:
            projection = RaceProjection()
        if not filter:
            filter = RacesFilter()

        try:
            log.info(f"Getting races with projection {projection} and filter {filter}")

            done = False
            races: List[Race] = []
            # iterate until no more races are found
            while not done:
                query = query_get_races(projection)

                variables = filter.to_dict()

                result = self._gql_client.execute(query, variable_values=variables)

                if result.get("races"):
                    log.info(
                        f"Received {len(result['races'])} races - attempting to get more..."
                    )
                    if parse_result:
                        races.extend(typedload.load(result["races"], List[Race]))
                    else:
                        races.extend(result["races"])

                    # change the offset to the next page
                    filter.offset += filter.limit
                else:
                    filter.offset = 0
                    log.debug("No more races found")
                    done = True

            return races

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
                            log.info(
                                f"Cannot query more than {filter.limit} - adjusting limit to {filter.limit} and trying again"
                            )
                            return self.get_races(projection, filter)
                        else:
                            log.error(f"{error}")
                    else:
                        log.error(f"{error}")
            else:
                log.error(f"Error querying Betwatch API: {e}")
            return []

    @overload
    def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]:
        ...

    @overload
    def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[True] = True,
    ) -> Union[Dict, None]:
        ...

    def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: bool = True,
    ) -> Union[Race, Dict, None]:
        # handle defaults
        if not projection:
            projection = RaceProjection(markets=True)
        query = query_get_race(projection)

        if parse_result:
            return self._get_race_by_id(race_id, query, parse_result=True)
        else:
            return self._get_race_by_id(race_id, query, parse_result=False)

    def get_races_today(
        self, projection: Optional[RaceProjection] = None
    ) -> List[Race]:
        """Get all races for today."""
        today = datetime.now()
        tomorrow = datetime.now() + timedelta(days=0)
        return self.get_races_between_dates(today, tomorrow, projection)

    @overload
    def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]:
        ...

    @overload
    def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: Literal[False] = False,
    ) -> Union[Dict, None]:
        ...

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: bool = True,
    ) -> Union[Race, Dict, None]:
        log.info(f"Getting race (id={race_id})")

        variables = {
            "id": race_id,
        }
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("race"):
            if parse_result:
                return typedload.load(result["race"], Race)
            else:
                return result["race"]
        return None

    def update_event_data(
        self, race_id: str, column_name: str, data: List[SelectionData]
    ):
        """
        Updates event data for a given race ID.

        Args:
            race_id (str): race id to be checked
            column_name (str): name of the column to be updated
            data (List[SelectionData]): list of selection data to be updated
        """

        log.info(f"Updating event data (id={race_id})")
        selection_data = [
            {"selectionId": d["selection_id"], "value": str(d["value"])} for d in data
        ]

        if not selection_data:
            raise ValueError("Cannot update event data with empty selection data")

        res = self._gql_client.execute(
            MUTATION_UPDATE_USER_EVENT_DATA,
            variable_values={
                "input": {
                    "eventId": race_id,
                    "customData": [
                        {"columnName": column_name, "selectionData": selection_data}
                    ],
                }
            },
        )
        log.debug(res)

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
