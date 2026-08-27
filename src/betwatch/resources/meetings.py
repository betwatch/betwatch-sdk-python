from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.meeting import Meeting, MeetingPage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Meetings:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> MeetingPage:
        return self._client._get(
            "/v2/meetings",
            list_query(
                sport=sport,
                country=country,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                after=after,
                before=before,
                limit=limit,
            ),
            MeetingPage,
        )

    def iter(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        limit: int | None = None,
    ) -> Iterator[Meeting]:
        """Walk every page of matching meeting rows.

        The cursor goes back to `/v2/meetings` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> MeetingPage:
            return self.list(
                sport=sport,
                country=country,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                limit=limit,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str) -> Meeting:
        return self._client._get("/v2/meetings/" + id, None, Meeting)


class AsyncMeetings:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> MeetingPage:
        return await self._client._aget(
            "/v2/meetings",
            list_query(
                sport=sport,
                country=country,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                after=after,
                before=before,
                limit=limit,
            ),
            MeetingPage,
        )

    async def iter(
        self,
        *,
        sport: Sequence[str] | str | None = None,
        country: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Meeting]:
        """Walk every page of matching meeting rows.

        The cursor goes back to `/v2/meetings` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> MeetingPage:
            return await self.list(
                sport=sport,
                country=country,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                limit=limit,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str) -> Meeting:
        return await self._client._aget("/v2/meetings/" + id, None, Meeting)
