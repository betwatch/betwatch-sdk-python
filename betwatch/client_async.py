import asyncio
import atexit
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Union

import backoff
import typedload
from aiohttp.client_exceptions import ClientError, ClientOSError
from gql import Client
from gql.client import AsyncClientSession, ReconnectingAsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as aiohttp_logger
from gql.transport.websockets import WebsocketsTransport
from gql.transport.websockets import log as websockets_logger
from graphql import DocumentNode
from websockets.exceptions import ConnectionClosedError

from betwatch.__about__ import __version__
from betwatch.queries import (
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    SUBSCRIPTION_BETFAIR_UPDATES,
    SUBSCRIPTION_RACES_UPDATES,
    query_get_race,
    query_get_races,
    subscription_race_price_updates,
)
from betwatch.types import (
    Race,
    RaceProjection,
    Bookmaker,
    BookmakerMarket,
    BetfairMarket,
)
from betwatch.types.race import RaceUpdate, SubscriptionUpdate


class BetwatchAsyncClient:
    def __init__(self, api_key: str, transport_logging_level: int = logging.WARNING):
        self.api_key = api_key

        self.connect()

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

        self._subscription_queue: asyncio.Queue[SubscriptionUpdate] = asyncio.Queue()
        self._subscriptions_betfair: Dict[str, List[asyncio.Task]] = {}
        self._subscriptions_prices: Dict[str, List[asyncio.Task]] = {}
        self._subscriptions_updates: Dict[Tuple[str, str], List[asyncio.Task]] = {}
        self._subscription_reconnect_task: asyncio.Task | None = (
            None  # handle resubscribing only once
        )

    def connect(self):
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

    async def disconnect(self):
        """Disconnect from the websocket connection."""
        logging.debug("disconnecting from client sessions")
        await self.__cleanup()

    async def __cleanup(self):
        """Gracefully close clients."""
        async with self._session_lock:
            try:
                self._http_session = None
                await self._gql_client.close_async()
            except Exception:
                pass
            try:
                self._websocket_session = None
                await self._gql_sub_client.close_async()
            except Exception:
                pass

    def __exit(self):
        """Close the client."""
        logging.info("closing connection to Betwatch API (may take a few seconds)")
        asyncio.run(self.__cleanup())

    async def reconnect(self):
        await self.disconnect()

        async with self._session_lock:
            if not self._subscription_reconnect_task:
                self._subscription_reconnect_task = asyncio.create_task(self._connect())

    async def _connect(self):
        self.connect()
        await asyncio.sleep(10)

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

    async def get_races_today(self, projection=RaceProjection()) -> List[Race]:
        """Get all races for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=0)).strftime("%Y-%m-%d")
        return await self.get_races_between_dates(today, tomorrow, projection)

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
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
        # convert to string if datetime
        if isinstance(date_from, datetime):
            date_from = date_from.strftime("%Y-%m-%d")
        if isinstance(date_to, datetime):
            date_to = date_to.strftime("%Y-%m-%d")

        logging.info(f"Getting races between {date_from} and {date_to}")

        session = await self._setup_http_session()

        query = query_get_races(projection)

        variables = {"dateFrom": date_from, "dateTo": date_to}

        result = await session.execute(query, variable_values=variables)

        if result.get("races"):
            logging.debug(f"Found {len(result['races'])} races")
            return typedload.load(result["races"], List[Race])

        return []

    async def get_race(
        self, race_id: str, projection=RaceProjection(markets=True)
    ) -> Union[Race, None]:
        """Get all details of a specific race by id.

        Args:
            race_id (str): The id of a race. This can be obtained from the `get_races` method.
            projection (RaceProjection, optional): The fields to return. Defaults to RaceProjection(markets=True).

        Returns:
            Union[Race, None]: The race object or None if the race is not found.
        """
        query = query_get_race(projection)
        return await self._get_race_by_id(race_id, query)

    async def listen(self):
        """Subscribe to any updates from your subscriptions"""
        if (
            len(self._subscriptions_prices) < 1
            and len(self._subscriptions_betfair) < 1
            and len(self._subscriptions_updates) < 1
        ):
            raise Exception("You must subscribe to a race before listening for updates")
        while True:
            update = await self._subscription_queue.get()
            self._subscription_queue.task_done()
            yield update

    async def subscribe_bookmaker_updates(
        self,
        race_id: str,
        projection=RaceProjection(markets=True),
    ):
        if race_id not in self._subscriptions_prices:
            self._subscriptions_prices[race_id] = []

        self._subscriptions_prices[race_id].append(
            asyncio.create_task(self._subscribe_bookmaker_updates(race_id, projection))
        )

    @backoff.on_exception(
        backoff.expo,
        (ConnectionClosedError, ClientError, ClientOSError),
        max_time=60,
        max_tries=5,
    )
    async def _subscribe_bookmaker_updates(
        self,
        race_id: str,
        projection=RaceProjection(markets=True),
    ):
        """Subscribe to price updates for a specific race.

        Args:
            race_id (str): The id of a specific race. This can be obtained from the `get_races` method.

        Yields:
            List[BookmakerMarket]: A list of bookmaker markets with updated prices.
        """
        try:
            session = await self._setup_websocket_session()

            query = subscription_race_price_updates(projection)
            variables = {"id": race_id}

            logging.info(f"Subscribing to price updates for {race_id}")

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("priceUpdates"):
                    update = SubscriptionUpdate(
                        race_id=race_id,
                        bookmaker_markets=typedload.load(
                            result["priceUpdates"], List[BookmakerMarket]
                        ),
                    )
                    self._subscription_queue.put_nowait(update)

        except (ConnectionClosedError, ClientOSError) as e:
            # handle connection closed errors by reconnecting
            # raise the error to trigger the backoff decorator and retry all subscriptions
            logging.warning("Connection closed, reconnecting...")

            await self.reconnect()
            raise e

    async def subscribe_betfair_updates(self, race_id: str):
        if race_id not in self._subscriptions_betfair:
            self._subscriptions_betfair[race_id] = []

        self._subscriptions_betfair[race_id].append(
            asyncio.create_task(self._subscribe_betfair_updates(race_id))
        )

    @backoff.on_exception(
        backoff.expo,
        (ConnectionClosedError, ClientError, ClientOSError),
        max_time=60,
        max_tries=5,
    )
    async def _subscribe_betfair_updates(
        self,
        race_id: str,
    ):
        """Subscribe to betfair price updates for a specific race.

        Args:
            race_id (str): The id of a specific race. This can be obtained from the `get_races` method.

        Yields:
            List[BetfairMarket]: A list of betfair markets with updated prices.
        """
        try:
            session = await self._setup_websocket_session()

            query = SUBSCRIPTION_BETFAIR_UPDATES
            variables = {"id": race_id}

            logging.info(f"Subscribing to betfair updates for {race_id}")

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("betfairUpdates"):
                    update = SubscriptionUpdate(
                        race_id=race_id,
                        betfair_markets=typedload.load(
                            result["betfairUpdates"], List[BetfairMarket]
                        ),
                    )
                    self._subscription_queue.put_nowait(update)

        except (ConnectionClosedError, ClientOSError) as e:
            # handle connection closed errors by reconnecting
            # raise the error to trigger the backoff decorator and retry all subscriptions
            logging.warning("Connection closed, reconnecting...")

            await self.reconnect()
            raise e

    async def subscribe_race_updates(self, date_from: str, date_to: str):
        if (date_from, date_to) not in self._subscriptions_updates:
            self._subscriptions_updates[(date_from, date_to)] = []

        self._subscriptions_updates[(date_from, date_to)].append(
            asyncio.create_task(self._subscribe_race_updates(date_from, date_to))
        )

    @backoff.on_exception(
        backoff.expo,
        (ConnectionClosedError, ClientError, ClientOSError),
        max_time=60,
        max_tries=5,
    )
    async def _subscribe_race_updates(self, date_from: str, date_to: str):
        try:
            session = await self._setup_websocket_session()

            query = SUBSCRIPTION_RACES_UPDATES
            variables = {"dateFrom": date_from, "dateTo": date_to}

            logging.info(f"Subscribing to race updates for {date_from} - {date_to}")

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("racesUpdates"):
                    ru = typedload.load(result["racesUpdates"], RaceUpdate)
                    update = SubscriptionUpdate(
                        race_id=ru.id,
                        race_update=ru,
                    )
                    self._subscription_queue.put_nowait(update)
        except (ConnectionClosedError, ClientOSError) as e:
            # handle connection closed errors by reconnecting
            # raise the error to trigger the backoff decorator and retry all subscriptions
            logging.warning("Connection closed, reconnecting...")

            await self.reconnect()
            raise e

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    async def _get_race_by_id(
        self, race_id: str, query: DocumentNode
    ) -> Union[Race, None]:
        logging.info(f"Getting race (id={race_id})")
        session = await self._setup_http_session()

        variables = {"id": race_id}

        result = await session.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None

    async def get_race_last_updated_times(
        self, race_id: str
    ) -> Dict[Bookmaker, datetime]:
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
