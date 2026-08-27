from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.venue import Venue, VenuePage
from ._pagination import awalk, walk

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
            "/v2/venues",
            list_query(sport=sport, country=country, after=after, before=before, limit=limit),
            VenuePage,
        )

    def iter(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        limit: int | None = None,
    ) -> Iterator[Venue]:
        """Walk every page of matching venue rows.

        The cursor goes back to `/v2/venues` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> VenuePage:
            return self.list(
                sport=sport,
                country=country,
                limit=limit,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str) -> Venue:
        return self._client._get("/v2/venues/" + id, None, Venue)


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
            "/v2/venues",
            list_query(sport=sport, country=country, after=after, before=before, limit=limit),
            VenuePage,
        )

    async def iter(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Venue]:
        """Walk every page of matching venue rows.

        The cursor goes back to `/v2/venues` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> VenuePage:
            return await self.list(
                sport=sport,
                country=country,
                limit=limit,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str) -> Venue:
        return await self._client._aget("/v2/venues/" + id, None, Venue)
