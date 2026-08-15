from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.venue import Venue, VenuePage

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Venues:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> VenuePage:
        return self._client._get(
            "/v1/venues",
            list_query(sport=sport, country=country, after=after, before=before, limit=limit),
            VenuePage,
        )

    def retrieve(self, id: str) -> Venue:
        return self._client._get("/v1/venues/" + id, None, Venue)


class AsyncVenues:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> VenuePage:
        return await self._client._aget(
            "/v1/venues",
            list_query(sport=sport, country=country, after=after, before=before, limit=limit),
            VenuePage,
        )

    async def retrieve(self, id: str) -> Venue:
        return await self._client._aget("/v1/venues/" + id, None, Venue)
