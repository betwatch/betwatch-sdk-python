import asyncio
import logging
from typing import List, Union
from gql import Client
from gql.transport.websockets import WebsocketsTransport
from gql.transport.aiohttp import AIOHTTPTransport
from gql.client import ReconnectingAsyncClientSession, AsyncClientSession
import typedload
from betwatch.queries import (
    QUERY_GET_RACE,
    QUERY_GET_RACES,
    SUBSCRIPTION_PRICE_UPDATES,
    SUBSCRIPTION_RACES_UPDATES,
)
from betwatch.types.markets import BookmakerMarket
from betwatch.types.race import Race
from betwatch.__about__ import __version__
import atexit
import backoff


class BetwatchAsyncClient:
    def __init__(self, api_key: str):
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
            fetch_schema_from_transport=True,
            execute_timeout=60,
            parse_results=True,
        )
        self._gql_client = Client(
            transport=self._gql_transport,
            fetch_schema_from_transport=True,
            execute_timeout=60,
            parse_results=True,
        )

        self._http_session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        # flag to indicate if we have entered the context manager
        self._session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        # register the cleaup function
        atexit.register(self.__exit)

    async def __cleanup(self):
        try:
            await self._gql_client.close_async()
        except Exception:
            pass
        try:
            await self._gql_sub_client.close_async()
        except Exception:
            pass

    def __exit(self):
        """Close the client."""
        asyncio.run(self.__cleanup())

    async def __aenter__(self):
        """Pass through to the underlying client's __aenter__ method."""
        self._session = await self._gql_sub_client.connect_async(reconnecting=True)
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Pass through to the underlying client's __aexit__ method."""
        await self._gql_sub_client.close_async()
        self._session = self._http_session
        return self._session

    async def __connect(self):
        """Connect to the GraphQL endpoint."""
        if not self._session:
            if not self._http_session:
                self._http_session = await self._gql_client.connect_async(
                    reconnecting=True
                )
                return self._http_session
            else:
                return self._http_session
        return self._session

    async def get_races(self, date_from: str, date_to: str) -> List[Race]:
        if not self._session:
            self._session = await self.__connect()

        query = QUERY_GET_RACES
        variables = {"dateFrom": date_from, "dateTo": date_to}

        result = await self._session.execute(query, variable_values=variables)
        if result.get("races"):
            return typedload.load(result["races"], List[Race])

        return []

    async def get_race(self, race_id: str, raise_exceptions=False) -> Union[Race, None]:
        # raise the exceptions for retrying, but then silently return none
        try:
            return await self.__get_race_by_id(race_id)
        except Exception as e:
            logging.error(f"Error getting race {race_id}: {e}")
            if raise_exceptions:
                raise e
            return None

    async def subscribe_price_updates(
        self,
        race_id: str,
    ):
        if not self._session:
            raise Exception(
                "Not connected to session. Use async with BetwatchAsyncClient():"
            )

        query = SUBSCRIPTION_PRICE_UPDATES
        variables = {"id": race_id}

        async for result in self._session.subscribe(query, variable_values=variables):
            if result.get("priceUpdates"):
                yield typedload.load(result["priceUpdates"], List[BookmakerMarket])

    async def subscribe_races_updates(self, date_from: str, date_to: str):
        if not self._session:
            raise Exception(
                "Not connected to session. Use async with BetwatchAsyncClient():"
            )

        query = SUBSCRIPTION_RACES_UPDATES
        variables = {"dateFrom": date_from, "dateTo": date_to}

        async for result in self._session.subscribe(query, variable_values=variables):
            if result.get("racesUpdates"):
                yield typedload.load(result["racesUpdates"], Race)

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    async def __get_race_by_id(self, race_id: str) -> Union[Race, None]:
        if not self._session:
            self._session = await self.__connect()

        query = QUERY_GET_RACE
        variables = {"id": race_id}

        result = await self._session.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None
