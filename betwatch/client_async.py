import asyncio
import atexit
import logging
import os
from datetime import datetime, timedelta
from time import monotonic
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, overload

import backoff
import typedload
from gql import Client
from gql.client import AsyncClientSession, ReconnectingAsyncClientSession
from gql.transport.exceptions import TransportError, TransportQueryError
from gql.transport.httpx import HTTPXAsyncTransport
from gql.transport.httpx import log as httpx_logger
from gql.transport.websockets import WebsocketsTransport
from gql.transport.websockets import log as websockets_logger
from graphql import DocumentNode
from httpx._exceptions import HTTPError
from typedload.exceptions import TypedloadException
from websockets.exceptions import ConnectionClosedError

from betwatch.__about__ import __version__
from betwatch.exceptions import APIKeyNotSetError
from betwatch.queries import (
    MUTATION_UPDATE_USER_EVENT_DATA,
    QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE,
    SUBSCRIPTION_BETFAIR_UPDATES,
    SUBSCRIPTION_RACES_UPDATES,
    query_get_race,
    query_get_race_from_bookmaker_market,
    query_get_races,
    subscription_race_price_updates,
)
from betwatch.types import (
    BetfairMarket,
    Bookmaker,
    BookmakerMarket,
    MeetingType,
    Race,
    RaceProjection,
    RaceUpdate,
    SubscriptionUpdate,
)
from betwatch.types.exceptions import NotEntitledError
from betwatch.types.filters import RacesFilter
from betwatch.types.updates import SelectionData

log = logging.getLogger(__name__)


class BetwatchAsyncClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        transport_logging_level: int = logging.WARNING,
        request_timeout: int = 60,
    ):
        if not api_key:
            api_key = os.environ.get("BETWATCH_API_KEY")
        if not api_key:
            raise APIKeyNotSetError()
        self.api_key = api_key

        self._gql_sub_transport: WebsocketsTransport
        self._gql_transport: HTTPXAsyncTransport
        self._gql_sub_client: Client
        self._gql_client: Client

        self.connect(request_timeout)

        self._http_session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        # flag to indicate if we have entered the context manager
        self._websocket_session: Union[
            None, ReconnectingAsyncClientSession, AsyncClientSession
        ] = None

        websockets_logger.setLevel(transport_logging_level)
        httpx_logger.setLevel(transport_logging_level)
        logging.getLogger("httpx").setLevel(transport_logging_level)
        logging.getLogger("httpcore").setLevel(transport_logging_level)

        # register the cleanup function to be called on exit
        atexit.register(self.__exit)

        # lock to prevent multiple sessions being created
        self._session_lock = asyncio.Lock()

        self._subscription_queue: asyncio.Queue[SubscriptionUpdate] = asyncio.Queue()
        self._subscriptions_betfair: Dict[str, asyncio.Task] = {}
        self._subscriptions_prices: Dict[str, asyncio.Task] = {}
        self._subscriptions_prices_type_args: Dict[
            str, Optional[List[Union[MeetingType, str]]]
        ] = {}
        self._subscriptions_prices_bookmaker_args: Dict[
            str, Optional[List[Union[Bookmaker, str]]]
        ] = {}
        self._subscriptions_prices_projection_args: Dict[
            str, Optional[RaceProjection]
        ] = {}

        self._subscriptions_updates: Dict[Tuple[str, str], asyncio.Task] = {}

        self._monitor_task: Union[asyncio.Task, None] = None
        self._last_reconnect: float = monotonic()

    def connect(self, request_timeout: int):
        sub_url = "wss://api.betwatch.com/sub"
        url = "https://api.betwatch.com/query"

        # Check for url environment override
        env_api_url = os.getenv("BETWATCH_API_URL")
        env_sub_url = os.getenv("BETWATCH_API_SUB_URL")
        if env_api_url:
            logging.info(f"Using API URL override: {env_api_url}")
            url = env_api_url
        if env_sub_url:
            logging.info(f"Using API SUB URL override: {env_sub_url}")
            sub_url = env_sub_url

        self._gql_sub_transport = WebsocketsTransport(
            url=sub_url,
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-sdk-python-{__version__}",
            },
            init_payload={"apiKey": self.api_key},
            ssl=sub_url.startswith("wss"),
        )
        self._gql_transport = HTTPXAsyncTransport(
            url=url,
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-sdk-python-{__version__}",
            },
            timeout=request_timeout,
        )
        # Create a GraphQL client using the defined transport
        self._gql_sub_client = Client(
            transport=self._gql_sub_transport,
            execute_timeout=request_timeout,
        )
        self._gql_client = Client(
            transport=self._gql_transport,
            execute_timeout=request_timeout,
        )
        log.debug("connected to client sessions")

    async def disconnect(self):
        """Disconnect from the websocket connection."""
        log.debug("disconnecting from client sessions")
        await self.__cleanup()
        if self._monitor_task:
            self._monitor_task.cancel()
        log.debug("disconnected from client sessions")

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
        log.debug("closing connection to Betwatch API (may take a few seconds)")
        asyncio.run(self.__cleanup())

    async def __aenter__(self):
        """Pass through to the underlying client's __aenter__ method."""
        log.debug("entering context manager")
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        log.debug("entered context manager")
        return self._websocket_session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Pass through to the underlying client's __aexit__ method."""
        log.debug("exiting context manager")
        await self.disconnect()
        log.debug("exited context manager")
        return self._websocket_session

    async def _setup_websocket_session(self):
        """Connect to websocket connection"""
        log.debug("setting up websocket session")
        async with self._session_lock:
            if not self._websocket_session:
                self._websocket_session = await self._gql_sub_client.connect_async(
                    reconnecting=True
                )
        log.debug("websocket session setup")
        return self._websocket_session

    async def _setup_http_session(self):
        """Setup the HTTP session."""
        async with self._session_lock:
            if not self._http_session:
                self._http_session = await self._gql_client.connect_async()
        return self._http_session

    @overload
    async def get_races_today(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[True] = True,
    ) -> List[Race]: ...

    @overload
    async def get_races_today(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[False] = False,
    ) -> List[Race]: ...

    async def get_races_today(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: bool = True,
    ) -> Union[List[Race], List[Dict]]:
        """Get all races for today."""
        # set defaults
        if not projection:
            projection = RaceProjection()
        if not filter:
            filter = RacesFilter()

        today = datetime.today().strftime("%Y-%m-%d")
        tomorrow = (datetime.today() + timedelta(days=0)).strftime("%Y-%m-%d")

        if parse_result:
            return await self.get_races_between_dates(
                today,
                tomorrow,
                projection=projection,
                filter=filter,
                parse_result=True,
            )
        else:
            return await self.get_races_between_dates(
                today,
                tomorrow,
                projection=projection,
                filter=filter,
                parse_result=False,
            )

    @overload
    async def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[True] = True,
    ) -> List[Race]: ...

    @overload
    async def get_races_between_dates(
        self,
        date_from: Union[str, datetime],
        date_to: Union[str, datetime],
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[False] = False,
    ) -> List[Race]: ...

    async def get_races_between_dates(
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
            date_to (Union[str, datetime]): Date to end at (inclusive   )
            projection (_type_, optional): The fields to return. Defaults to RaceProjection().
            filter (_type_, optional): The filter to apply. Defaults to RacesFilter().

        Returns:
            List[Race]: List of races that match the criteria
        """
        # set defaults
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
        if parse_result:
            return await self.get_races(projection, filter, parse_result=True)
        else:
            return await self.get_races(projection, filter, parse_result=False)

    @overload
    async def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[True] = True,
    ) -> List[Race]: ...

    @overload
    async def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: Literal[False] = False,
    ) -> List[Dict]: ...

    @backoff.on_exception(backoff.expo, (HTTPError))
    async def get_races(
        self,
        projection: Optional[RaceProjection] = None,
        filter: Optional[RacesFilter] = None,
        parse_result: bool = True,
    ) -> Union[List[Race], List[Dict]]:
        # set defaults
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
                session = await self._setup_http_session()

                query = query_get_races(projection)

                variables = filter.to_dict()

                result = await session.execute(query, variable_values=variables)

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
        except TypedloadException as e:
            log.error(f"Error parsing Betwatch API response: {e}")
            raise e
        except (HTTPError, TimeoutError) as e:
            log.warning(f"Error reaching Betwatch API: {e}")
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
                            log.info(
                                f"Cannot query more than {filter.limit} - adjusting limit to {filter.limit} and trying again"
                            )
                            return await self.get_races(projection, filter)
                        else:
                            log.error(f"{error}")
                    else:
                        log.error(f"{error}")
            else:
                log.error(f"Error querying Betwatch API: {e}")
            return []

    @overload
    async def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]: ...

    @overload
    async def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[False] = False,
    ) -> Union[Race, None]: ...

    async def get_race(
        self,
        race_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: bool = True,
    ) -> Union[Race, Dict, None]:
        """Get all details of a specific race by id.

        Args:
            race_id (str): The id of a race. This can be obtained from the `get_races` method.
            projection (RaceProjection, optional): The fields to return. Defaults to RaceProjection(markets=True).

        Returns:
            Union[Race, None]: The race object or None if the race is not found.
        """
        # set defaults
        if not projection:
            projection = RaceProjection(markets=True)
        query = query_get_race(projection)
        if parse_result:
            return await self._get_race_by_id(race_id, query, parse_result=True)
        else:
            return await self._get_race_by_id(race_id, query, parse_result=False)

    @overload
    async def get_race_from_bookmaker_market(
        self,
        market_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]: ...

    @overload
    async def get_race_from_bookmaker_market(
        self,
        market_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: Literal[False] = False,
    ) -> Union[Race, None]: ...

    async def get_race_from_bookmaker_market(
        self,
        market_id: str,
        projection: Optional[RaceProjection] = None,
        parse_result: bool = True,
    ) -> Union[Race, Dict, None]:
        """Get all details of a specific race by id.

        Args:
            race_id (str): The id of a race. This can be obtained from the `get_races` method.
            projection (RaceProjection, optional): The fields to return. Defaults to RaceProjection(markets=True).

        Returns:
            Union[Race, None]: The race object or None if the race is not found.
        """
        # set defaults
        if not projection:
            projection = RaceProjection(markets=True)
        query = query_get_race_from_bookmaker_market(projection)
        if parse_result:
            return await self._get_race_from_bookmaker_market(
                market_id, query, parse_result=True
            )
        else:
            return await self._get_race_from_bookmaker_market(
                market_id, query, parse_result=False
            )

    async def _monitor(self):
        """Monitor the subscription tasks and restart them if they fail"""
        log.debug("Starting subscription monitor")
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
                                    log.warning(f"Subscription task closed: {err}")
                                    # reset the connection
                                    if self._websocket_session:
                                        await self.disconnect()

                                    # if the user is not entitled to the data, don't retry
                                    # check if err is of type NotEntitledError
                                    if isinstance(err, NotEntitledError):
                                        log.warning(
                                            "You are not entitled to subscriptions. Please contact api@betwatch.com to upgrade your API key."
                                        )
                                        del d[key]
                                        continue

                            except asyncio.InvalidStateError:
                                pass

                            log.warning(
                                f"Retrying subscription task for {key if key else 'all races'}"
                            )

                            # replace the task in the dict with a new one
                            if d == self._subscriptions_prices:
                                race_types = self._subscriptions_prices_type_args[key]
                                bookmakers = self._subscriptions_prices_bookmaker_args[key]
                                projection = self._subscriptions_prices_projection_args[key]
                                d[key] = asyncio.create_task(
                                    self._subscribe_bookmaker_updates(key, race_types=race_types, bookmakers=bookmakers, projection=projection)
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
                log.debug("Subscription monitor cancelled")
                return
            except Exception as e:
                log.debug(f"Error in subscription monitor: {e}")
                raise e

    async def listen(self):
        """Subscribe to any updates from your subscriptions with enhanced queue monitoring."""
        if (
            len(self._subscriptions_prices) < 1
            and len(self._subscriptions_betfair) < 1
            and len(self._subscriptions_updates) < 1
        ):
            raise Exception("You must subscribe to a race before listening for updates")

        # Configuration for queue monitoring
        QUEUE_SIZE_THRESHOLD = 100  # Threshold for queue size to trigger monitoring
        SUSTAINED_PERIOD = 10  # Seconds the queue must remain above threshold
        WARNING_INTERVAL = timedelta(seconds=30)  # Minimum interval between warnings

        last_warning_time = datetime.now()
        high_queue_start = None  # Timestamp when queue first exceeded threshold

        # Start the monitor task
        self._monitor_task = asyncio.create_task(self._monitor())

        try:
            while True:
                try:
                    log.debug("Waiting for subscription update")
                    update = await self._subscription_queue.get()
                    current_time = monotonic()
                    queue_size = self._subscription_queue.qsize()

                    # Check if queue size exceeds threshold
                    if queue_size > QUEUE_SIZE_THRESHOLD:
                        if high_queue_start is None:
                            high_queue_start = current_time  # Mark the start time
                            log.debug(f"Queue size exceeded threshold: {queue_size}")
                        elif (current_time - high_queue_start) > SUSTAINED_PERIOD:
                            # Check if enough time has passed since last warning
                            if datetime.now() - last_warning_time > WARNING_INTERVAL:
                                log.warning(
                                    f"Processing falling behind: Queue size has been "
                                    f">{QUEUE_SIZE_THRESHOLD} for over {SUSTAINED_PERIOD} seconds "
                                    f"(current size: {queue_size})"
                                )
                                last_warning_time = datetime.now()
                                # Reset the start time to avoid repeated warnings for the same sustained period
                                high_queue_start = current_time
                    else:
                        if high_queue_start is not None:
                            log.debug(f"Queue size back to normal: {queue_size}")
                        high_queue_start = (
                            None  # Reset if queue size drops below threshold
                        )

                    self._subscription_queue.task_done()
                    yield update
                    log.debug("Subscription update received")

                except asyncio.CancelledError:
                    log.info("Shutting down subscription websocket...")
                    break  # Exit the loop gracefully

        finally:
            # Ensure that the monitor task is cancelled when listen is exited
            if not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    log.debug("Monitor task cancelled successfully")

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
            log.info(
                f"Not subscribed to {race_id if race_id else 'all races'} bookmaker updates"
            )
            return

        self._subscriptions_prices[race_id].cancel()
        del self._subscriptions_prices[race_id]
        del self._subscriptions_prices_type_args[race_id]
        del self._subscriptions_prices_bookmaker_args[race_id]
        del self._subscriptions_prices_projection_args[race_id]
        log.info(
            f"Unsubscribed from {race_id if race_id else 'all races'} bookmaker updates"
        )

    async def subscribe_bookmaker_updates(
        self,
        race_id: str,
        race_types: Optional[
            List[
                Union[
                    Literal["Thoroughbred"],
                    Literal["Harness"],
                    Literal["Greyhound"],
                ]
            ]
        ] = None,
        projection: Optional[RaceProjection] = None,
        bookmakers: Optional[List[Union[Bookmaker, str]]] = None,
    ):
        # set defaults
        if not projection:
            projection = RaceProjection(markets=True)

        if race_id in self._subscriptions_prices:
            log.info(
                f"Already subscribed to {race_id if race_id else 'all races'} bookmaker updates"
            )
            return

        # make sure the total subscriptions is less than 10
        if len(self._subscriptions_prices) >= 10:
            raise Exception(
                "Cannot subscribe to more than 10 races at one time. Use an empty race_id to subscribe to all races in one subscription"
            )

        _race_types = [str(t) for t in race_types] if race_types else []

        self._subscriptions_prices[race_id] = asyncio.create_task(
            self._subscribe_bookmaker_updates(race_id,race_types= _race_types, projection=projection, bookmakers=bookmakers)
        )
        self._subscriptions_prices_type_args[race_id] = _race_types
        self._subscriptions_prices_bookmaker_args[race_id] = bookmakers
        self._subscriptions_prices_projection_args[race_id] = projection

    async def _subscribe_bookmaker_updates(
        self,
        race_id: str,
        race_types: Optional[List[Union[MeetingType, str]]] = None,
        bookmakers: Optional[List[Union[Bookmaker, str]]] = None,
        projection: Optional[RaceProjection] = None,
    ):
        """Subscribe to price updates for a specific race.

        Args:
            race_id (str): The id of a specific race. This can be obtained from the `get_races` method.
            race_types (List[Union[MeetingType, str]], optional): The types of races to subscribe to. Defaults to None.
            projection (RaceProjection, optional): The fields to return. Defaults to RaceProjection(markets=True).

        Yields:
            List[BookmakerMarket]: A list of bookmaker markets with updated prices.
        """
        # set defaults
        if not projection:
            projection = RaceProjection(markets=True)

        try:
            session = await self._setup_websocket_session()

            query = subscription_race_price_updates(projection)
            variables: dict[str, Any] = {"id": race_id}
            if race_types:
                variables["types"] = [str(t) for t in race_types]
            else:
                variables["types"] = []
            if bookmakers:
                variables["bookmakers"] = [str(b) for b in bookmakers]

            log.info(
                f"Subscribing to bookmaker updates for {race_id if race_id else 'all races'} "
                f"with race types: {race_types if race_types else 'all races'} and bookmakers: {bookmakers if bookmakers else 'all bookmakers'}"
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
            log.debug(f"Error subscribing to bookmaker updates: {e}")

            # check if the user is entitled to this data
            if "does not have access" in e.args[0]:
                raise NotEntitledError(
                    "API key is not entitled to websocket subscriptions"
                ) from e
        except asyncio.CancelledError:
            await self.unsubscribe_bookmaker_updates(race_id)
            return
        except ConnectionClosedError as e:
            log.debug(f"Error on bookmaker prices subscription: {e}")
        except Exception as e:
            log.debug(f"Error subscribing to bookmaker updates: {e}")

    async def unsubscribe_betfair_updates(self, race_id: str):
        if race_id not in self._subscriptions_betfair:
            log.info(
                f"Not subscribed to {race_id if race_id else 'all races'} betfair updates"
            )
            return

        self._subscriptions_betfair[race_id].cancel()
        del self._subscriptions_betfair[race_id]
        log.info(
            f"Unsubscribed from {race_id if race_id else 'all races'} betfair updates"
        )

    async def subscribe_betfair_updates(self, race_id: str):
        if race_id in self._subscriptions_betfair:
            log.info(
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

            log.info(
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
            log.debug(f"Error subscribing to betfair updates: {e}")

            # check if the user is entitled to this data
            if "does not have access" in e.args[0]:
                raise NotEntitledError(
                    "API key is not entitled to websocket subscriptions"
                ) from e
        except asyncio.CancelledError:
            await self.unsubscribe_betfair_updates(race_id)
            return
        except ConnectionClosedError as e:
            log.debug(f"Error on betfair subscription: {e}")

    async def unsubscribe_race_updates(self, date_from: str, date_to: str):
        if (date_from, date_to) not in self._subscriptions_updates:
            log.info(f"Not subscribed to races updates for {date_from} - {date_to}")
            return

        self._subscriptions_updates[(date_from, date_to)].cancel()
        del self._subscriptions_updates[(date_from, date_to)]
        log.info(f"Unsubscribed from races updates for {date_from} - {date_to}")

    async def subscribe_race_updates(self, date_from: str, date_to: str):
        if (date_from, date_to) in self._subscriptions_updates:
            log.info(f"Already subscribed to races updates for {date_from} - {date_to}")
            return

        self._subscriptions_updates[(date_from, date_to)] = asyncio.create_task(
            self._subscribe_race_updates(date_from, date_to)
        )

    async def _subscribe_race_updates(self, date_from: str, date_to: str):
        try:
            session = await self._setup_websocket_session()

            query = SUBSCRIPTION_RACES_UPDATES
            variables = {"dateFrom": date_from, "dateTo": date_to}

            log.debug(f"Subscribing to race updates for {date_from} - {date_to}")

            async for result in session.subscribe(query, variable_values=variables):
                if result.get("racesUpdates"):
                    ru = typedload.load(result["racesUpdates"], RaceUpdate)
                    update = SubscriptionUpdate(
                        race_id=ru.id,
                        race_update=ru,
                    )
                    self._subscription_queue.put_nowait(update)

        except TransportError as e:
            log.debug(f"Error subscribing to race updates: {e}")
        except asyncio.CancelledError:
            await self.unsubscribe_race_updates(date_from, date_to)
            return
        except ConnectionClosedError as e:
            log.debug(f"Error on race updates subscription: {e}")

    @overload
    async def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]: ...

    @overload
    async def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: Literal[False] = False,
    ) -> Union[Dict, None]: ...

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    async def _get_race_by_id(
        self,
        race_id: str,
        query: DocumentNode,
        parse_result: bool = False,
    ) -> Union[Race, Dict, None]:
        log.info(f"Getting race (id={race_id})")
        session = await self._setup_http_session()
        variables = {
            "id": race_id,
        }

        result = await session.execute(query, variable_values=variables)

        if result.get("race"):
            if parse_result:
                return typedload.load(result["race"], Race)
            else:
                return result["race"]
        return None

    @overload
    async def _get_race_from_bookmaker_market(
        self,
        market_id: str,
        query: DocumentNode,
        parse_result: Literal[True] = True,
    ) -> Union[Race, None]: ...

    @overload
    async def _get_race_from_bookmaker_market(
        self,
        market_id: str,
        query: DocumentNode,
        parse_result: Literal[False] = False,
    ) -> Union[Dict, None]: ...

    @backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
    async def _get_race_from_bookmaker_market(
        self,
        market_id: str,
        query: DocumentNode,
        parse_result: bool = False,
    ) -> Union[Race, Dict, None]:
        log.info(f"Getting race from bookmaker market (id={market_id})")
        session = await self._setup_http_session()
        variables = {
            "id": market_id,
        }

        result = await session.execute(query, variable_values=variables)

        if result.get("raceFromBookmakerMarket"):
            if parse_result:
                return typedload.load(result["raceFromBookmakerMarket"], Race)
            else:
                return result["raceFromBookmakerMarket"]
        return None

    async def update_event_data(
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
        session = await self._setup_http_session()
        selection_data = [
            {"selectionId": d["selection_id"], "value": str(d["value"])} for d in data
        ]

        if not selection_data:
            raise ValueError("Cannot update event data with empty selection data")

        res = await session.execute(
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

        if isinstance(race, Race) and race.links:
            return {
                link.bookmaker: link.last_successful_price_update
                for link in race.links
                if link.bookmaker and link.last_successful_price_update
            }
        elif isinstance(race, Dict) and "links" in race:
            return {
                link["bookmaker"]: link["last_successful_price_update"]
                for link in race["links"]
                if link["bookmaker"] and link["last_successful_price_update"]
            }

        return {}
