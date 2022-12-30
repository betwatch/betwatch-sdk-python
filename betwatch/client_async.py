import asyncio
import atexit
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Union

import backoff
import typedload
from gql import Client
from gql.client import AsyncClientSession, ReconnectingAsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as aiohttp_logger
from gql.transport.websockets import WebsocketsTransport
from gql.transport.websockets import log as websockets_logger

from betwatch.__about__ import __version__
from betwatch.queries import (
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    QUERY_GET_RACE,
    QUERY_GET_RACES,
    QUERY_GET_RACES_WITH_MARKETS,
    SUBSCRIPTION_PRICE_UPDATES,
    SUBSCRIPTION_RACES_UPDATES,
)
from betwatch.types import Race, RaceProjection
from betwatch.types.markets import BookmakerMarket


class BetwatchAsyncClient:
    def __init__(self, api_key: str, transport_logging_level: int = logging.WARNING):
        self.api_key = api_key
        self._gql_sub_transport = WebsocketsTransport(
            url="wss://api.betwatch.com/sub",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-python-{__version__}",
            },
            init_payload={"apiKey": self.api_key},
            ack_timeout=60,
        )
        self._gql_transport = AIOHTTPTransport(
            url="https://api.betwatch.com/query",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-python-{__version__}",
            },
        )
        # Create a GraphQL client using the defined transport
        self._gql_sub_client = Client(
            transport=self._gql_sub_transport,
            execute_timeout=60,
        )
        self._gql_client = Client(
            transport=self._gql_transport,
            execute_timeout=60,
        )

        self._http_session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        # flag to indicate if we have entered the context manager
        self._websocket_session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        websockets_logger.setLevel(transport_logging_level)
        aiohttp_logger.setLevel(transport_logging_level)

        # register the cleanup function to be called on exit
        atexit.register(self.__exit)

        # lock to prevent multiple sessions being created
        self._session_lock = asyncio.Lock()

    async def disconnect(self):
        """Disconnect from the websocket connection."""
        async with self._session_lock:
            await self._gql_client.close_async()
            await self._gql_sub_client.close_async()
            self._http_session = None
            self._websocket_session = None

    async def __cleanup(self):
        """Gracefully close clients."""
        # try:
        #     await self._gql_client.close_async()
        # except Exception:
        #     pass
        # try:
        #     await self._gql_sub_client.close_async()
        # except Exception:
        #     pass
        async with self._session_lock:
            try:
                await self._gql_transport.close()
            except Exception:
                pass
            try:
                await self._gql_sub_transport.close()
            except Exception:
                pass
            try:
                if self._http_session:
                    await self._http_session.client.close_async()
            except Exception:
                pass

    def __exit(self):
        """Close the client."""
        logging.info("closing connection to Betwatch API (may take a few seconds)")
        asyncio.run(self.__cleanup())

    async def __aenter__(self):
        """Pass through to the underlying client's __aenter__ method."""
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        return self._websocket_session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Pass through to the underlying client's __aexit__ method."""
        async with self._session_lock:
            if self._websocket_session:
                self._websocket_session = (
                    await self._websocket_session.client.close_async()
                )
        return self._websocket_session

    async def _setup_websocket_session(self):
        """Connect to websocket connection"""
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        return self._websocket_session

    async def _setup_http_session(self):
        """Setup the HTTP session."""
        async with self._session_lock:
            if not self._http_session:
                self._http_session = await self._gql_client.connect_async()
        return self._http_session

    async def get_races_today(self) -> List[Race]:
        """Get all races for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return await self.get_races_between_dates(today, tomorrow)

    async def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection=RaceProjection(),
    ) -> List[Race]:
        """Get a list of races in between two dates.

        Args:
            date_from (Union[str, datetime]): Date to start from (inclusive)
            date_to (Union[str, datetime]): Date to end at (inclusive   )
            projection (_type_, optional): The fields to return. Defaults to RaceProjection().

        Returns:
            List[Race]: List of races that match the criteria
        """
        logging.info(f"getting races between {date_from} and {date_to}")

        session = await self._setup_http_session()

        query = QUERY_GET_RACES_WITH_MARKETS if projection.markets else QUERY_GET_RACES

        # convert to string if datetime
        if isinstance(date_from, datetime):
            date_from = date_from.strftime("%Y-%m-%d")
        if isinstance(date_to, datetime):
            date_to = date_to.strftime("%Y-%m-%d")

        variables = {"dateFrom": date_from, "dateTo": date_to}

        result = await session.execute(query, variable_values=variables)

        if result.get("races"):
            logging.debug(f"Found {len(result['races'])} races")
            return typedload.load(result["races"], List[Race])

        return []

    async def get_race(self, race_id: str) -> Union[Race, None]:
        """Get all details of a specific race by id.

        Args:
            race_id (str): The id of a race. This can be obtained from the `get_races` method.

        Returns:
            Union[Race, None]: The race object or None if the race is not found.
        """
        return await self._get_race_by_id(race_id)

    async def subscribe_price_updates(
        self,
        race_id: str,
    ):
        """Subscribe to price updates for a specific race.

        Args:
            race_id (str): The id of a specific race. This can be obtained from the `get_races` method.

        Yields:
            List[BookmakerMarket]: A list of bookmaker markets with updated prices.
        """
        session = await self._setup_websocket_session()

        query = SUBSCRIPTION_PRICE_UPDATES
        variables = {"id": race_id}

        async for result in session.subscribe(query, variable_values=variables):
            if result.get("priceUpdates"):
                yield typedload.load(result["priceUpdates"], List[BookmakerMarket])

    async def subscribe_races_updates(self, date_from: str, date_to: str):
        session = await self._setup_websocket_session()

        query = SUBSCRIPTION_RACES_UPDATES
        variables = {"dateFrom": date_from, "dateTo": date_to}

        async for result in session.subscribe(query, variable_values=variables):
            if result.get("racesUpdates"):
                yield typedload.load(result["racesUpdates"], Race)

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    async def _get_race_by_id(
        self, race_id: str, query=QUERY_GET_RACE
    ) -> Union[Race, None]:
        logging.info(f"Getting race (id={race_id})")
        session = await self._setup_http_session()

        variables = {"id": race_id}

        result = await session.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None

    async def get_race_last_updated_times(self, race_id: str) -> Dict[str, datetime]:
        """Get the last time each bookmaker was checked for a price update.
           This does not mean that the price was updated, just that the bookmaker was checked.

        Args:
            race_id (str): race id to be checked

        Returns:
            Dict[str, datetime]: dictionary with bookmaker name as key and datetime as value
        """
        race = await self._get_race_by_id(
            race_id, QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE
        )
        if not race or not race.links:
            return {}

        return {
            link.bookmaker: link.last_successful_price_update
            for link in race.links
            if link.bookmaker and link.last_successful_price_update
        }
