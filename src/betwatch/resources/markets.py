from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.market import Market, MarketPage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Markets:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        event: Sequence[str] | str,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> MarketPage:
        """List markets for one event. Example: `client.markets.list(event=event_id)`"""
        if not event:
            raise FilterRequiredError("markets", "event", "client.markets.list(event=event_id)")
        return self._client._get(
            "/v1/markets",
            list_query(event=event, after=after, before=before, limit=limit),
            MarketPage,
        )

    def iter(
        self,
        *,
        event: Sequence[str] | str,
        limit: int | None = None,
    ) -> Iterator[Market]:
        """Walk every page of matching market rows.

        The cursor goes back to `/v1/markets` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> MarketPage:
            return self.list(
                event=event,
                limit=limit,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str) -> Market:
        return self._client._get("/v1/markets/" + id, None, Market)


class AsyncMarkets:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        event: Sequence[str] | str,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> MarketPage:
        if not event:
            raise FilterRequiredError("markets", "event", "client.markets.list(event=event_id)")
        return await self._client._aget(
            "/v1/markets",
            list_query(event=event, after=after, before=before, limit=limit),
            MarketPage,
        )

    async def iter(
        self,
        *,
        event: Sequence[str] | str,
        limit: int | None = None,
    ) -> AsyncIterator[Market]:
        """Walk every page of matching market rows.

        The cursor goes back to `/v1/markets` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> MarketPage:
            return await self.list(
                event=event,
                limit=limit,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str) -> Market:
        return await self._client._aget("/v1/markets/" + id, None, Market)
