from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any, TypeVar

import httpx

from ._base_client import (
    DEFAULT_MAX_RETRIES,
    STREAM_READ_TIMEOUT,
    decode_model,
    default_headers,
    flatten,
    parse_retry_after,
    raise_if_error,
    require_key,
    resolve_base_url,
    retry_after_seconds,
    safe_json,
    should_retry_status,
    stream_headers_and_query,
)
from ._exceptions import APIConnectionError, APITimeoutError, ResyncRequired
from ._progress import (
    DEFAULT_INTERVAL,
    AsyncBootstrapReporter,
    BootstrapReporter,
    ProgressCallback,
)
from ._ratelimit import RateLimit
from ._streaming import aiter_sse, frame_from_sse, iter_sse
from .resources.competitors import AsyncCompetitors, Competitors
from .resources.entrants import AsyncEntrants, Entrants
from .resources.events import AsyncEvents, Events
from .resources.markets import AsyncMarkets, Markets
from .resources.meetings import AsyncMeetings, Meetings
from .resources.odds import AsyncOddsResource, OddsResource
from .resources.outcomes import AsyncOutcomes, Outcomes
from .resources.sources import AsyncSources, Sources
from .resources.venues import AsyncVenues, Venues
from .types.common import as_sequence
from .types.enums import ErrorCodes, IncludeFlag, SnapshotMode, Sport
from .types.snapshot import EventSnapshot
from .types.stream import ReadyFrame, StreamFrame, SyncFrame, frame_name

_T = TypeVar("_T")

# The cursor is unusable and reconnecting with it would loop forever. Both
# codes are declared on `streamRacing` as 409, so either signal is sufficient
# on its own: the status is the contract's, the codes say which of the two
# happened. `tests/test_contract_spec.py` pins both against openapi.json.
RESYNC_STATUS = 409
RESYNC_CODES = frozenset({ErrorCodes.CURSOR_EXPIRED, ErrorCodes.CURSOR_SCOPE_CHANGED})


def _stream_backoff(attempt: int) -> float:
    """Full-jitter wait, 0–0.5s then doubling to 8s."""
    return random.random() * min(8.0, 0.5 * (2**attempt))


class Stream:
    """Live `/v1/stream`. Use as a context manager.

    Transport disconnects reconnect with backoff and `Last-Event-ID`.
    HTTP, decode, and `resync` failures surface immediately.
    """

    def __init__(
        self,
        client: Betwatch,
        params: dict[str, Any],
        *,
        reconnect: bool,
        progress: ProgressCallback | None = None,
        progress_interval: float = DEFAULT_INTERVAL,
    ) -> None:
        self._client = client
        self._params = dict(params)
        self._reconnect = reconnect
        self._response: httpx.Response | None = None
        self._attempt = 0
        self.cursor: str | None = params.get("cursor")
        self.trace_id: str | None = None
        self._synced = False
        # Only a full snapshot has a bootstrap; a cursor resume is live at once.
        self._reporter = (
            BootstrapReporter(progress, interval=progress_interval)
            if progress is not None and params.get("snapshot") != "none"
            else None
        )

    def _open(self) -> httpx.Response:
        extra, query = stream_headers_and_query(self._params, self.cursor)
        headers = {**self._client._headers, **extra}
        request = self._client._raw.build_request(
            "GET",
            "/v1/stream",
            params=flatten(query),
            headers=headers,
            timeout=httpx.Timeout(STREAM_READ_TIMEOUT, connect=10.0),
        )
        response = self._client._raw.send(request, stream=True)
        if response.status_code >= 400:
            raw = response.read()
            response.close()
            from ._exceptions import error_for_status

            err = error_for_status(
                response.status_code,
                path="/v1/stream",
                body=safe_json(httpx.Response(response.status_code, content=raw)),
                request_id=response.headers.get("x-request-id") or None,
                trace_id=response.headers.get("x-trace-id") or None,
                retry_after=parse_retry_after(response),
                rate_limit=RateLimit.from_headers(response.headers),
            )
            if response.status_code == RESYNC_STATUS or err.code in RESYNC_CODES:
                raise ResyncRequired(self.cursor, err.code or "conflict") from err
            raise err
        self.trace_id = response.headers.get("x-trace-id") or None
        # The stream declares the budget headers too, so a long-lived consumer
        # can see its remaining monthly quota without issuing a REST call.
        self._client.rate_limit = (
            RateLimit.from_headers(response.headers) or self._client.rate_limit
        )
        return response

    def _open_with_retry(self) -> httpx.Response:
        while True:
            try:
                return self._open()
            except httpx.TransportError as exc:
                if not self._reconnect:
                    raise APIConnectionError("/v1/stream", exc) from exc
            wait = _stream_backoff(self._attempt)
            self._attempt += 1
            time.sleep(wait)

    def __enter__(self) -> Stream:
        self._response = self._open_with_retry()
        if self._reporter is not None:
            self._reporter.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._reporter is not None:
            self._reporter.stop()
        if self._response is not None:
            self._response.close()
            self._response = None

    def __iter__(self) -> Iterator[StreamFrame]:
        try:
            while True:
                if self._response is None:
                    self._response = self._open_with_retry()
                try:
                    for sse in iter_sse(self._response.iter_bytes()):
                        if sse.id is not None:
                            self.cursor = sse.id
                        frame = frame_from_sse(sse)
                        if self._reporter is not None and frame is None and sse.event == "ping":
                            # Swallowed as data, but during a bootstrap a ping is
                            # the proof the connection is alive rather than hung.
                            self._reporter.record_ping()
                        if frame is not None:
                            self._attempt = 0
                            if self._reporter is not None:
                                if isinstance(frame, SyncFrame):
                                    self._reporter.stop(synced=True)
                                    self._reporter = None
                                elif not isinstance(frame, ReadyFrame):
                                    # `ready` is the connection opening, not
                                    # snapshot data — counting it would hide the
                                    # "nothing has arrived yet" state entirely.
                                    self._reporter.record(frame_name(frame))
                            if isinstance(frame, SyncFrame):
                                self._synced = True
                            yield frame
                    self.close()
                    if not self._reconnect:
                        return
                    if not self._synced and self._params.get("snapshot") == "full":
                        raise ResyncRequired(self.cursor, "incomplete_snapshot")
                    continue
                except ResyncRequired:
                    self.close()
                    raise
                except httpx.TransportError as exc:
                    self.close()
                    if not self._reconnect:
                        raise APIConnectionError("/v1/stream", exc) from exc
                    if not self._synced and self._params.get("snapshot") == "full":
                        # No resumable position exists until `sync`, so the whole
                        # snapshot starts again and every frame so far is lost.
                        # Say so: a silent restart is indistinguishable from a
                        # bootstrap that is merely slow.
                        self.cursor = None
                        if self._reporter is not None:
                            self._reporter.record_restart()
                    continue
        except KeyboardInterrupt:
            raise
        finally:
            self.close()


class AsyncStream:
    def __init__(
        self,
        client: AsyncBetwatch,
        params: dict[str, Any],
        *,
        reconnect: bool,
        progress: ProgressCallback | None = None,
        progress_interval: float = DEFAULT_INTERVAL,
    ) -> None:
        self._client = client
        self._params = dict(params)
        self._reconnect = reconnect
        self._response: httpx.Response | None = None
        self._attempt = 0
        self.cursor: str | None = params.get("cursor")
        self.trace_id: str | None = None
        self._synced = False
        self._reporter = (
            AsyncBootstrapReporter(progress, interval=progress_interval)
            if progress is not None and params.get("snapshot") != "none"
            else None
        )

    async def _open(self) -> httpx.Response:
        extra, query = stream_headers_and_query(self._params, self.cursor)
        headers = {**self._client._headers, **extra}
        request = self._client._raw.build_request(
            "GET",
            "/v1/stream",
            params=flatten(query),
            headers=headers,
            timeout=httpx.Timeout(STREAM_READ_TIMEOUT, connect=10.0),
        )
        response = await self._client._raw.send(request, stream=True)
        if response.status_code >= 400:
            raw = await response.aread()
            await response.aclose()
            from ._exceptions import error_for_status

            err = error_for_status(
                response.status_code,
                path="/v1/stream",
                body=safe_json(httpx.Response(response.status_code, content=raw)),
                request_id=response.headers.get("x-request-id") or None,
                trace_id=response.headers.get("x-trace-id") or None,
                retry_after=parse_retry_after(response),
                rate_limit=RateLimit.from_headers(response.headers),
            )
            if response.status_code == RESYNC_STATUS or err.code in RESYNC_CODES:
                raise ResyncRequired(self.cursor, err.code or "conflict") from err
            raise err
        self.trace_id = response.headers.get("x-trace-id") or None
        # The stream declares the budget headers too, so a long-lived consumer
        # can see its remaining monthly quota without issuing a REST call.
        self._client.rate_limit = (
            RateLimit.from_headers(response.headers) or self._client.rate_limit
        )
        return response

    async def _open_with_retry(self) -> httpx.Response:
        while True:
            try:
                return await self._open()
            except httpx.TransportError as exc:
                if not self._reconnect:
                    raise APIConnectionError("/v1/stream", exc) from exc
            wait = _stream_backoff(self._attempt)
            self._attempt += 1
            await asyncio.sleep(wait)

    async def __aenter__(self) -> AsyncStream:
        self._response = await self._open_with_retry()
        if self._reporter is not None:
            self._reporter.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._reporter is not None:
            self._reporter.stop()
        if self._response is not None:
            await self._response.aclose()
            self._response = None

    async def __aiter__(self) -> AsyncIterator[StreamFrame]:
        try:
            while True:
                if self._response is None:
                    self._response = await self._open_with_retry()
                try:
                    async for sse in aiter_sse(self._response.aiter_bytes()):
                        if sse.id is not None:
                            self.cursor = sse.id
                        frame = frame_from_sse(sse)
                        if self._reporter is not None and frame is None and sse.event == "ping":
                            # Swallowed as data, but during a bootstrap a ping is
                            # the proof the connection is alive rather than hung.
                            self._reporter.record_ping()
                        if frame is not None:
                            self._attempt = 0
                            if self._reporter is not None:
                                if isinstance(frame, SyncFrame):
                                    self._reporter.stop(synced=True)
                                    self._reporter = None
                                elif not isinstance(frame, ReadyFrame):
                                    # `ready` is the connection opening, not
                                    # snapshot data — counting it would hide the
                                    # "nothing has arrived yet" state entirely.
                                    self._reporter.record(frame_name(frame))
                            if isinstance(frame, SyncFrame):
                                self._synced = True
                            yield frame
                    await self.close()
                    if not self._reconnect:
                        return
                    if not self._synced and self._params.get("snapshot") == "full":
                        raise ResyncRequired(self.cursor, "incomplete_snapshot")
                    continue
                except ResyncRequired:
                    await self.close()
                    raise
                except httpx.TransportError as exc:
                    await self.close()
                    if not self._reconnect:
                        raise APIConnectionError("/v1/stream", exc) from exc
                    if not self._synced and self._params.get("snapshot") == "full":
                        # No resumable position exists until `sync`, so the whole
                        # snapshot starts again and every frame so far is lost.
                        # Say so: a silent restart is indistinguishable from a
                        # bootstrap that is merely slow.
                        self.cursor = None
                        if self._reporter is not None:
                            self._reporter.record_restart()
                    continue
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        finally:
            await self.close()


class Watch:
    """Snapshot one event, then follow its stream. The usual agent workflow.

    ```python
    with client.watch(event_id) as live:
        print(live.snapshot.event.name)
        for frame in live:
            ...
    ```
    """

    def __init__(
        self,
        client: Betwatch,
        event_id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
        reconnect: bool = True,
    ) -> None:
        self._client = client
        self._event_id = event_id
        self._source = source
        self._include: Sequence[IncludeFlag] | IncludeFlag | None = include
        self._reconnect = reconnect
        self.snapshot: EventSnapshot | None = None
        self._stream: Stream | None = None
        self._resyncs = 0

    def _open(self) -> None:
        if self._stream is not None:
            self._stream.close()
        self.snapshot = self._client.events.snapshot(
            self._event_id,
            source=self._source,
            include=self._include,
        )
        self._stream = self._client.follow(self.snapshot, reconnect=self._reconnect)
        self._stream.__enter__()

    def __enter__(self) -> Watch:
        self._open()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.__exit__(*exc)

    def __iter__(self) -> Iterator[StreamFrame]:
        if self._stream is None:
            raise RuntimeError("Watch must be used as a context manager")
        while True:
            try:
                yield from self._stream
                return
            except ResyncRequired:
                self._resyncs += 1
                if not self._reconnect or self._resyncs > 8:
                    raise
                self._open()


class AsyncWatch:
    def __init__(
        self,
        client: AsyncBetwatch,
        event_id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
        reconnect: bool = True,
    ) -> None:
        self._client = client
        self._event_id = event_id
        self._source = source
        self._include: Sequence[IncludeFlag] | IncludeFlag | None = include
        self._reconnect = reconnect
        self.snapshot: EventSnapshot | None = None
        self._stream: AsyncStream | None = None
        self._resyncs = 0

    async def _open(self) -> None:
        if self._stream is not None:
            await self._stream.close()
        self.snapshot = await self._client.events.snapshot(
            self._event_id,
            source=self._source,
            include=self._include,
        )
        self._stream = self._client.follow(self.snapshot, reconnect=self._reconnect)
        await self._stream.__aenter__()

    async def __aenter__(self) -> AsyncWatch:
        await self._open()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._stream is not None:
            await self._stream.__aexit__(*exc)

    async def __aiter__(self) -> AsyncIterator[StreamFrame]:
        if self._stream is None:
            raise RuntimeError("AsyncWatch must be used as a context manager")
        while True:
            try:
                async for frame in self._stream:
                    yield frame
                return
            except ResyncRequired:
                self._resyncs += 1
                if not self._reconnect or self._resyncs > 8:
                    raise
                await self._open()


def _stream_params(
    *,
    cursor: str | None,
    snapshot: SnapshotMode,
    sport: Sequence[Sport] | Sport | None,
    country: Sequence[str] | str | None,
    meeting: Sequence[str] | str | None,
    event: Sequence[str] | str | None,
    venue: Sequence[str] | str | None,
    market: Sequence[str] | str | None,
    outcome: Sequence[str] | str | None,
    entrant: Sequence[str] | str | None,
    source: Sequence[str] | str | None,
    start_from: str | None,
    start_to: str | None,
) -> dict[str, Any]:
    return {
        "cursor": cursor,
        "snapshot": snapshot,
        "sport": as_sequence(sport),
        "country": as_sequence(country),
        "meeting": as_sequence(meeting),
        "event": as_sequence(event),
        "venue": as_sequence(venue),
        "market": as_sequence(market),
        "outcome": as_sequence(outcome),
        "entrant": as_sequence(entrant),
        "source": as_sequence(source),
        "startFrom": start_from,
        "startTo": start_to,
    }


class Betwatch:
    """Sync client for the public `/v1` REST + SSE API.

    ```python
    with Betwatch() as client:                     # BETWATCH_API_KEY
        for event in client.events.list(limit=5):
            with client.watch(event.id) as live:
                for frame in live:
                    ...
    ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: httpx.Timeout | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        self.api_key = require_key(api_key)
        self.base_url = resolve_base_url(base_url)
        self.max_retries = max_retries
        self.rate_limit: RateLimit | None = None
        self._headers = default_headers(self.api_key)
        self._raw = httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout or httpx.Timeout(30.0, connect=10.0),
        )
        self.events = Events(self)
        self.odds = OddsResource(self)
        self.entrants = Entrants(self)
        self.markets = Markets(self)
        self.outcomes = Outcomes(self)
        self.meetings = Meetings(self)
        self.venues = Venues(self)
        self.competitors = Competitors(self)
        self.sources = Sources(self)

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> Betwatch:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: Mapping[str, Any] | None, model: type[_T]) -> _T:
        query = flatten(params or {})
        for attempt in range(self.max_retries + 1):
            try:
                response = self._raw.get(path, params=query)
            except httpx.TimeoutException as exc:
                if attempt >= self.max_retries:
                    raise APITimeoutError(path, exc) from exc
                time.sleep(min(0.5 * (2**attempt), 8.0))
                continue
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise APIConnectionError(path, exc) from exc
                time.sleep(min(0.5 * (2**attempt), 8.0))
                continue
            if attempt < self.max_retries and should_retry_status(response):
                time.sleep(retry_after_seconds(response, attempt))
                continue
            self.rate_limit = RateLimit.from_headers(response.headers) or self.rate_limit
            raise_if_error(response, path)
            return decode_model(path, response.content, model)
        raise AssertionError("unreachable request loop")

    def follow(self, snapshot: EventSnapshot, *, reconnect: bool = True) -> Stream:
        """Subscribe after a REST snapshot. Sends the snapshot cursor as Last-Event-ID."""
        return self.stream(
            event=snapshot.stream.event,
            source=snapshot.stream.source,
            cursor=snapshot.stream.cursor,
            snapshot="none",
            reconnect=reconnect,
        )

    def watch(
        self,
        event_id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
        reconnect: bool = True,
    ) -> Watch:
        """Snapshot one event and follow its stream. Preferred agent entrypoint."""
        return Watch(
            self,
            event_id,
            source=source,
            include=include,
            reconnect=reconnect,
        )

    def stream(
        self,
        *,
        cursor: str | None = None,
        snapshot: SnapshotMode = "full",
        reconnect: bool = True,
        sport: Sequence[Sport] | Sport | None = None,
        country: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        event: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        progress: ProgressCallback | None = None,
        progress_interval: float = DEFAULT_INTERVAL,
    ) -> Stream:
        """Open `/v1/stream`. Prefer `watch()` or `follow(snapshot)`.

        `progress=print_progress` reports the bootstrap while `snapshot=full`
        is being delivered — a broad scope sends nothing for tens of seconds
        before the first frame, and looks hung without it.
        """
        return Stream(
            self,
            _stream_params(
                cursor=cursor,
                snapshot=snapshot,
                sport=sport,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                market=market,
                outcome=outcome,
                entrant=entrant,
                source=source,
                start_from=start_from,
                start_to=start_to,
            ),
            reconnect=reconnect,
            progress=progress,
            progress_interval=progress_interval,
        )


class AsyncBetwatch:
    """Async twin of `Betwatch`. Same resource tree and method names."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: httpx.Timeout | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        self.api_key = require_key(api_key)
        self.base_url = resolve_base_url(base_url)
        self.max_retries = max_retries
        self.rate_limit: RateLimit | None = None
        self._headers = default_headers(self.api_key)
        self._raw = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout or httpx.Timeout(30.0, connect=10.0),
        )
        self.events = AsyncEvents(self)
        self.odds = AsyncOddsResource(self)
        self.entrants = AsyncEntrants(self)
        self.markets = AsyncMarkets(self)
        self.outcomes = AsyncOutcomes(self)
        self.meetings = AsyncMeetings(self)
        self.venues = AsyncVenues(self)
        self.competitors = AsyncCompetitors(self)
        self.sources = AsyncSources(self)

    async def close(self) -> None:
        await self._raw.aclose()

    async def __aenter__(self) -> AsyncBetwatch:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _aget(self, path: str, params: Mapping[str, Any] | None, model: type[_T]) -> _T:
        query = flatten(params or {})
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._raw.get(path, params=query)
            except httpx.TimeoutException as exc:
                if attempt >= self.max_retries:
                    raise APITimeoutError(path, exc) from exc
                await asyncio.sleep(min(0.5 * (2**attempt), 8.0))
                continue
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise APIConnectionError(path, exc) from exc
                await asyncio.sleep(min(0.5 * (2**attempt), 8.0))
                continue
            if attempt < self.max_retries and should_retry_status(response):
                await asyncio.sleep(retry_after_seconds(response, attempt))
                continue
            self.rate_limit = RateLimit.from_headers(response.headers) or self.rate_limit
            raise_if_error(response, path)
            return decode_model(path, response.content, model)
        raise AssertionError("unreachable request loop")

    def follow(self, snapshot: EventSnapshot, *, reconnect: bool = True) -> AsyncStream:
        return self.stream(
            event=snapshot.stream.event,
            source=snapshot.stream.source,
            cursor=snapshot.stream.cursor,
            snapshot="none",
            reconnect=reconnect,
        )

    def watch(
        self,
        event_id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
        reconnect: bool = True,
    ) -> AsyncWatch:
        return AsyncWatch(
            self,
            event_id,
            source=source,
            include=include,
            reconnect=reconnect,
        )

    def stream(
        self,
        *,
        cursor: str | None = None,
        snapshot: SnapshotMode = "full",
        reconnect: bool = True,
        sport: Sequence[Sport] | Sport | None = None,
        country: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        event: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        progress: ProgressCallback | None = None,
        progress_interval: float = DEFAULT_INTERVAL,
    ) -> AsyncStream:
        return AsyncStream(
            self,
            _stream_params(
                cursor=cursor,
                snapshot=snapshot,
                sport=sport,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                market=market,
                outcome=outcome,
                entrant=entrant,
                source=source,
                start_from=start_from,
                start_to=start_to,
            ),
            reconnect=reconnect,
            progress=progress,
            progress_interval=progress_interval,
        )
