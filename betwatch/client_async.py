import asyncio
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Union

import backoff
import typedload
from gql import Client
from gql.client import AsyncClientSession, ReconnectingAsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport

from betwatch.__about__ import __version__
from betwatch.queries import (
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    QUERY_GET_RACE,
    QUERY_GET_RACES,
    QUERY_GET_RACES_WITH_MARKETS,
    SUBSCRIPTION_PRICE_UPDATES,
    SUBSCRIPTION_RACES_UPDATES,
)
from betwatch.types.markets import BookmakerMarket
from betwatch.types.projection import RaceProjection
from betwatch.types.race import Race


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

        # register the cleanup function to be called on exit
        atexit.register(self.__exit)

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

    async def get_todays_races(self) -> List[Race]:
        """Get all races for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return await self.get_races(today, tomorrow)

    async def get_races(
        self, date_from: str, date_to: str, projection=RaceProjection()
    ) -> List[Race]:
        if not self._session:
            self._session = await self.__connect()

        query = QUERY_GET_RACES_WITH_MARKETS if projection.markets else QUERY_GET_RACES
        variables = {"dateFrom": date_from, "dateTo": date_to}

        result = await self._session.execute(query, variable_values=variables)
        if result.get("races"):
            return typedload.load(result["races"], List[Race])

        return []

    async def get_race(self, race_id: str) -> Union[Race, None]:
        return await self._get_race_by_id(race_id)

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
    async def _get_race_by_id(
        self, race_id: str, query=QUERY_GET_RACE
    ) -> Union[Race, None]:
        if not self._session:
            self._session = await self.__connect()

        variables = {"id": race_id}

        result = await self._session.execute(query, variable_values=variables)

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
