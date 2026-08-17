from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.entrant import Entrant, EntrantPage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Entrants:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        event: Sequence[str] | str | None = None,
        competitor: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> EntrantPage:
        """List entrants for one event, or every start for one competitor.

        Example: `client.entrants.list(event=event_id)`
        """
        if not event and not competitor:
            raise FilterRequiredError(
                "entrants",
                "event or competitor",
                "client.entrants.list(event=event_id)",
            )
        return self._client._get(
            "/v1/entrants",
            list_query(
                event=event,
                competitor=competitor,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            EntrantPage,
        )

    def iter(
        self,
        *,
        event: Sequence[str] | str | None = None,
        competitor: Sequence[str] | str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> Iterator[Entrant]:
        """Walk every page of matching entrant rows.

        The cursor goes back to `/v1/entrants` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> EntrantPage:
            return self.list(
                event=event,
                competitor=competitor,
                limit=limit,
                include=include,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Entrant:
        return self._client._get("/v1/entrants/" + id, list_query(include=include), Entrant)


class AsyncEntrants:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        event: Sequence[str] | str | None = None,
        competitor: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> EntrantPage:
        if not event and not competitor:
            raise FilterRequiredError(
                "entrants",
                "event or competitor",
                "client.entrants.list(event=event_id)",
            )
        return await self._client._aget(
            "/v1/entrants",
            list_query(
                event=event,
                competitor=competitor,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            EntrantPage,
        )

    async def iter(
        self,
        *,
        event: Sequence[str] | str | None = None,
        competitor: Sequence[str] | str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> AsyncIterator[Entrant]:
        """Walk every page of matching entrant rows.

        The cursor goes back to `/v1/entrants` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> EntrantPage:
            return await self.list(
                event=event,
                competitor=competitor,
                limit=limit,
                include=include,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Entrant:
        return await self._client._aget("/v1/entrants/" + id, list_query(include=include), Entrant)
