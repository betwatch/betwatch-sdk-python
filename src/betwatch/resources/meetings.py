from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.meeting import Meeting, MeetingPage

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
            "/v1/meetings",
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

    def retrieve(self, id: str) -> Meeting:
        return self._client._get("/v1/meetings/" + id, None, Meeting)


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
            "/v1/meetings",
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

    async def retrieve(self, id: str) -> Meeting:
        return await self._client._aget("/v1/meetings/" + id, None, Meeting)
