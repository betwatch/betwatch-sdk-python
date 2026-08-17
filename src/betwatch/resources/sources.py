from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.source import Source, SourcePage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Sources:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> SourcePage:
        return self._client._get(
            "/v1/sources",
            list_query(after=after, before=before, limit=limit, source=source),
            SourcePage,
        )

    def iter(
        self,
        *,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> Iterator[Source]:
        """Walk every page of matching source rows.

        The cursor goes back to `/v1/sources` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> SourcePage:
            return self.list(
                limit=limit,
                source=source,
                after=after,
            )

        return walk(fetch)


class AsyncSources:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> SourcePage:
        return await self._client._aget(
            "/v1/sources",
            list_query(after=after, before=before, limit=limit, source=source),
            SourcePage,
        )

    async def iter(
        self,
        *,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> AsyncIterator[Source]:
        """Walk every page of matching source rows.

        The cursor goes back to `/v1/sources` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> SourcePage:
            return await self.list(
                limit=limit,
                source=source,
                after=after,
            )

        async for row in awalk(fetch):
            yield row
