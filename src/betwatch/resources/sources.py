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
        event: str | None = None,
    ) -> SourcePage:
        return self._client._get(
            "/v2/sources",
            list_query(after=after, before=before, limit=limit, source=source, event=event),
            SourcePage,
        )

    def iter(
        self,
        *,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
        event: str | None = None,
    ) -> Iterator[Source]:
        """Walk every page of matching source rows.

        The cursor goes back to `/v2/sources` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> SourcePage:
            return self.list(
                limit=limit,
                source=source,
                event=event,
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
        event: str | None = None,
    ) -> SourcePage:
        return await self._client._aget(
            "/v2/sources",
            list_query(after=after, before=before, limit=limit, source=source, event=event),
            SourcePage,
        )

    async def iter(
        self,
        *,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
        event: str | None = None,
    ) -> AsyncIterator[Source]:
        """Walk every page of matching source rows.

        The cursor goes back to `/v2/sources` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> SourcePage:
            return await self.list(
                limit=limit,
                source=source,
                event=event,
                after=after,
            )

        async for row in awalk(fetch):
            yield row
