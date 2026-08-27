from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.odds import Odds, OddsPage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class OddsResource:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        event: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> OddsPage:
        """List current odds. Requires event, entrant, meeting, or venue.

        Example: `client.odds.list(event=event_id, include="history")`
        """
        if not event and not entrant and not meeting and not venue:
            raise FilterRequiredError(
                "odds",
                "event, entrant, meeting, or venue",
                "client.odds.list(event=event_id)",
            )
        return self._client._get(
            "/v2/odds",
            list_query(
                event=event,
                entrant=entrant,
                meeting=meeting,
                venue=venue,
                market=market,
                outcome=outcome,
                source=source,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            OddsPage,
        )

    def iter(
        self,
        *,
        event: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> Iterator[Odds]:
        """Walk every page of matching odds rows.

        The cursor goes back to `/v2/odds` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> OddsPage:
            return self.list(
                event=event,
                entrant=entrant,
                meeting=meeting,
                venue=venue,
                market=market,
                outcome=outcome,
                source=source,
                limit=limit,
                include=include,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str) -> Odds:
        return self._client._get("/v2/odds/" + id, None, Odds)


class AsyncOddsResource:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        event: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> OddsPage:
        if not event and not entrant and not meeting and not venue:
            raise FilterRequiredError(
                "odds",
                "event, entrant, meeting, or venue",
                "client.odds.list(event=event_id)",
            )
        return await self._client._aget(
            "/v2/odds",
            list_query(
                event=event,
                entrant=entrant,
                meeting=meeting,
                venue=venue,
                market=market,
                outcome=outcome,
                source=source,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            OddsPage,
        )

    async def iter(
        self,
        *,
        event: Sequence[str] | str | None = None,
        entrant: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        market: Sequence[str] | str | None = None,
        outcome: Sequence[str] | str | None = None,
        source: Sequence[str] | str | None = None,
        limit: int | None = None,
        include: Sequence[str] | str | None = None,
    ) -> AsyncIterator[Odds]:
        """Walk every page of matching odds rows.

        The cursor goes back to `/v2/odds` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> OddsPage:
            return await self.list(
                event=event,
                entrant=entrant,
                meeting=meeting,
                venue=venue,
                market=market,
                outcome=outcome,
                source=source,
                limit=limit,
                include=include,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str) -> Odds:
        return await self._client._aget("/v2/odds/" + id, None, Odds)
