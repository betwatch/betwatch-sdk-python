import asyncio
import atexit
import logging
from datetime import datetime, timedelta
from time import monotonic
from typing import Dict, List, Tuple, Union

import backoff
import typedload
from aiohttp.client_exceptions import ClientError
from aiohttp.web_exceptions import HTTPClientError, HTTPServerError
from gql import Client
from gql.client import AsyncClientSession, ReconnectingAsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as aiohttp_logger
from gql.transport.exceptions import TransportError, TransportQueryError
from gql.transport.websockets import WebsocketsTransport
from gql.transport.websockets import log as websockets_logger
from graphql import DocumentNode
from typedload.exceptions import TypedloadException

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
    BetfairMarket,
    Bookmaker,
    BookmakerMarket,
    Race,
    RaceProjection,
    RaceUpdate,
    SubscriptionUpdate,
)
from betwatch.types.filters import RacesFilter


class BetwatchAsyncClient:
    def __init__(self, api_key: str, transport_logging_level: int = logging.WARNING):
        self.api_key = api_key

        self._gql_sub_transport: WebsocketsTransport
        self._gql_transport: AIOHTTPTransport
        self._gql_sub_client: Client
        self._gql_client: Client

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
        self._subscriptions_betfair: Dict[str, asyncio.Task] = {}
        self._subscriptions_prices: Dict[str, asyncio.Task] = {}
        self._subscriptions_updates: Dict[Tuple[str, str], asyncio.Task] = {}

        self._monitor_task: Union[asyncio.Task, None] = None
        self._last_reconnect: float = monotonic()

    def connect(self):
        logging.debug("connecting to client sessions")
        self._gql_sub_transport = WebsocketsTransport(
            url="wss://api.betwatch.com/sub",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-sdk-python-{__version__}",
            },
            init_payload={"apiKey": self.api_key},
            pong_timeout=60,
            ping_interval=5,
        )
        self._gql_transport = AIOHTTPTransport(
            url="https://api.betwatch.com/query",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-sdk-python-{__version__}",
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
        logging.debug("connected to client sessions")

    async def disconnect(self):
        """Disconnect from the websocket connection."""
        logging.debug("disconnecting from client sessions")
        await self.__cleanup()
        logging.debug("disconnected from client sessions")

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

    async def __aenter__(self):
        """Pass through to the underlying client's __aenter__ method."""
        logging.debug("entering context manager")
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        logging.debug("entered context manager")
        return self._websocket_session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Pass through to the underlying client's __aexit__ method."""
        logging.debug("exiting context manager")
        async with self._session_lock:
            if self._websocket_session:
                self._websocket_session = (
                    await self._websocket_session.client.close_async()
                )
        logging.debug("exited context manager")
        return self._websocket_session

    async def _setup_websocket_session(self):
        """Connect to websocket connection"""
        logging.debug("setting up websocket session")
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        logging.debug("websocket session setup")
        return self._websocket_session

    async def _setup_http_session(self):
        """Setup the HTTP session."""
        async with self._session_lock:
            if not self._http_session:
                self._http_session = await self._gql_client.connect_async()
        return self._http_session

    async def get_races_today(
        self, projection=RaceProjection(), filter=RacesFilter()
    ) -> List[Race]:
        """Get all races for today."""
        today = datetime.today().strftime("%Y-%m-%d")
        tomorrow = (datetime.today() + timedelta(days=0)).strftime("%Y-%m-%d")
        return await self.get_races_between_dates(today, tomorrow, projection, filter)

    async def get_races_between_dates(
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
            filter (_type_, optional): The filter to apply. Defaults to RacesFilter().

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
        return await self.get_races(projection, filter)

    async def query_races(self, projection=RaceProjection(), filter=RacesFilter()):
        pass

    @backoff.on_exception(backoff.expo, (ClientError, HTTPClientError, HTTPServerError))
    async def get_races(
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
                session = await self._setup_http_session()

                query = query_get_races(projection)

                variables = filter.to_dict()

                result = await session.execute(query, variable_values=variables)

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
        except TypedloadException as e:
            logging.error(f"Error parsing Betwatch API response: {e}")
            raise e
        except (ClientError, HTTPClientError, HTTPServerError, TimeoutError) as e:
            logging.warning(f"Error reaching Betwatch API: {e}")
            raise e
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
                            return await self.get_races(projection, filter)
                        else:
                            logging.error(f"{error}")
                    else:
                        logging.error(f"{error}")
            else:
                logging.error(f"Error querying Betwatch API: {e}")
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

    async def _monitor(self):
        """Monitor the subscription tasks and restart them if they fail"""
        logging.debug("Starting subscription monitor")
        while True:
            try:
                await asyncio.sleep(1)
                for d in [
                    self._subscriptions_prices,
                    self._subscriptions_updates,
                    self._subscriptions_betfair,
                ]:
                    for key, task in d.items():
                        if task.done():
                            # check for errors
                            try:
                                err = task.exception()
                                if err:
                                    logging.error(f"Error in subscription task: {err}")
                                    # reset the connection
                                    if self._websocket_session:
                                        await self.disconnect()
                            except asyncio.InvalidStateError:
                                pass

                            logging.info(f"Restarting subscription task for {key}")

                            # replace the task in the dict with a new one
                            if d == self._subscriptions_prices:
                                d[key] = asyncio.create_task(
                                    self._subscribe_bookmaker_updates(key)
                                )
                            elif d == self._subscriptions_updates:
                                d[key] = asyncio.create_task(
                                    self._subscribe_race_updates(*key)
                                )
                            elif d == self._subscriptions_betfair:
                                d[key] = asyncio.create_task(
                                    self._subscribe_betfair_updates(key)
                                )

                            # update last reconnect
                            self._last_reconnect = monotonic()
            except asyncio.CancelledError:
                logging.debug("Subscription monitor cancelled")
                return
            except Exception as e:
                logging.error(f"Error in subscription monitor: {e}")
                raise e

    async def listen(self):
        """Subscribe to any updates from your subscriptions"""
        if (
            len(self._subscriptions_prices) < 1
            and len(self._subscriptions_betfair) < 1
            and len(self._subscriptions_updates) < 1
        ):
            raise Exception("You must subscribe to a race before listening for updates")

        # dont spam the user with warnings of queue size
        last_warning = datetime.now()

        # start monitor
        self._monitor_task = asyncio.create_task(self._monitor())

        while True:
            try:
                logging.debug("Waiting for subscription update")
                update = await self._subscription_queue.get()
                self._subscription_queue.task_done()
                yield update
                logging.debug("Subscription update received")

                # check if we are falling behind
                if (
                    self._subscription_queue.qsize() > 25
                    and (datetime.now() - last_warning).seconds > 10
                ):
                    logging.warning(
                        f"Subscription queue is {self._subscription_queue.qsize()} items behind"
                    )
                    last_warning = datetime.now()
            except asyncio.CancelledError:
                logging.info("Subscription queue cancelled")
                return

    def get_subscribed_race_ids(self) -> List[str]:
        """Get a list of all subscribed races"""
        unique = list(self._subscriptions_prices.keys()) + list(
            self._subscriptions_betfair.keys()
        )
        return list(set(unique)) if unique else []

    async def unsubscribe_race(self, race_id: str):
        await self.unsubscribe_betfair_updates(race_id)
        await self.unsubscribe_bookmaker_updates(race_id)

    async def unsubscribe_bookmaker_updates(self, race_id: str):
        if race_id not in self._subscriptions_prices:
            logging.info(
                f"Not subscribed to {race_id if race_id else 'all races'} bookmaker updates"
            )
            return

        self._subscriptions_prices[race_id].cancel()
        del self._subscriptions_prices[race_id]
        logging.info(
            f"Unsubscribed from {race_id if race_id else 'all races'} bookmaker updates"
        )

    async def subscribe_bookmaker_updates(
        self,
        race_id: str,
        projection=RaceProjection(markets=True),
    ):
        if race_id in self._subscriptions_prices:
            logging.info(
                f"Already subscribed to {race_id if race_id else 'all races'} bookmaker updates"
            )
            return

        # make sure the total subscriptions is less than 10
        if len(self._subscriptions_prices) >= 10:
            raise Exception(
                "Cannot subscribe to more than 10 races at one time. Use an empty race_id to subscribe to all races in one subscription"
            )

        self._subscriptions_prices[race_id] = asyncio.create_task(
            self._subscribe_bookmaker_updates(race_id, projection)
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

            logging.info(
                f"Subscribing to bookmaker updates for {race_id if race_id else 'all races'}"
            )

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("priceUpdates"):
                    update = SubscriptionUpdate(
                        race_id=race_id,
                        bookmaker_markets=typedload.load(
                            result["priceUpdates"], List[BookmakerMarket]
                        ),
                    )

                    self._subscription_queue.put_nowait(update)
        except TransportError as e:
            logging.error(f"Error subscribing to bookmaker updates: {e}")
        except asyncio.CancelledError:
            await self.unsubscribe_bookmaker_updates(race_id)
            return

    async def unsubscribe_betfair_updates(self, race_id: str):
        if race_id not in self._subscriptions_betfair:
            logging.info(
                f"Not subscribed to {race_id if race_id else 'all races'} betfair updates"
            )
            return

        self._subscriptions_betfair[race_id].cancel()
        del self._subscriptions_betfair[race_id]
        logging.info(
            f"Unsubscribed from {race_id if race_id else 'all races'} betfair updates"
        )

    async def subscribe_betfair_updates(self, race_id: str):
        if race_id in self._subscriptions_betfair:
            logging.info(
                f"Already subscribed to {race_id if race_id else 'all races'} betfair updates"
            )
            return

        # make sure the total subscriptions is less than 10
        if len(self._subscriptions_betfair) >= 10:
            raise Exception(
                "Cannot subscribe to more than 10 races at one time. Use an empty race_id to subscribe to all races in one subscription"
            )

        self._subscriptions_betfair[race_id] = asyncio.create_task(
            self._subscribe_betfair_updates(race_id)
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

            logging.info(
                f"Subscribing to betfair updates for {race_id if race_id else 'all races'}"
            )

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("betfairUpdates"):
                    update = SubscriptionUpdate(
                        race_id=race_id,
                        betfair_markets=typedload.load(
                            result["betfairUpdates"], List[BetfairMarket]
                        ),
                    )
                    self._subscription_queue.put_nowait(update)

        except TransportError as e:
            logging.error(f"Error subscribing to betfair updates: {e}")
        except asyncio.CancelledError:
            await self.unsubscribe_betfair_updates(race_id)
            return

    async def unsubscribe_race_updates(self, date_from: str, date_to: str):
        if (date_from, date_to) not in self._subscriptions_updates:
            logging.info(f"Not subscribed to races updates for {date_from} - {date_to}")
            return

        self._subscriptions_updates[(date_from, date_to)].cancel()
        del self._subscriptions_updates[(date_from, date_to)]
        logging.info(f"Unsubscribed from races updates for {date_from} - {date_to}")

    async def subscribe_race_updates(self, date_from: str, date_to: str):
        if (date_from, date_to) in self._subscriptions_updates:
            logging.info(
                f"Already subscribed to races updates for {date_from} - {date_to}"
            )
            return

        self._subscriptions_updates[(date_from, date_to)] = asyncio.create_task(
            self._subscribe_race_updates(date_from, date_to)
        )

    async def _subscribe_race_updates(self, date_from: str, date_to: str):
        try:
            session = await self._setup_websocket_session()

            query = SUBSCRIPTION_RACES_UPDATES
            variables = {"dateFrom": date_from, "dateTo": date_to}

            logging.debug(f"Subscribing to race updates for {date_from} - {date_to}")

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("racesUpdates"):
                    ru = typedload.load(result["racesUpdates"], RaceUpdate)
                    update = SubscriptionUpdate(
                        race_id=ru.id,
                        race_update=ru,
                    )
                    self._subscription_queue.put_nowait(update)

        except TransportError as e:
            logging.error(f"Error subscribing to race updates: {e}")
        except asyncio.CancelledError:
            await self.unsubscribe_race_updates(date_from, date_to)
            return

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
