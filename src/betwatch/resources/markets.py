from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.market import Market, MarketPage

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

    async def retrieve(self, id: str) -> Market:
        return await self._client._aget("/v1/markets/" + id, None, Market)
