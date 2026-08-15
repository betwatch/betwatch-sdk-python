from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import default_event_window, list_query
from ..types.enums import EventStatus, IncludeFlag, Sport
from ..types.event import Event, EventPage
from ..types.snapshot import EventSnapshot

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


def _event_list_query(
    *,
    sport: Sequence[Sport] | Sport | None,
    status: Sequence[EventStatus] | EventStatus | None,
    country: Sequence[str] | str | None,
    meeting: Sequence[str] | str | None,
    event: Sequence[str] | str | None,
    venue: Sequence[str] | str | None,
    start_from: str | None,
    start_to: str | None,
    after: str | None,
    before: str | None,
    limit: int | None,
    include: Sequence[str] | str | None,
) -> dict[str, object]:
    if start_from is None and start_to is None and after is None and before is None:
        start_from, start_to = default_event_window()
    return list_query(
        sport=sport,
        status=status,
        country=country,
        meeting=meeting,
        event=event,
        venue=venue,
        start_from=start_from,
        start_to=start_to,
        after=after,
        before=before,
        limit=limit,
        include=include,
    )


class Events:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        sport: Sequence[Sport] | Sport | None = None,
        status: Sequence[EventStatus] | EventStatus | None = None,
        country: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        event: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> EventPage:
        """List events. `include` accepts `coverage` and/or `racing`.

        When neither `start_from` nor `start_to` is set, the client asks for
        the last 12 hours through the next 24 so a bare `limit=5` is today's
        card — not the oldest race in the entitlement window.

        `status` is the public lifecycle word (`open`, `final`, …). There is
        no default: omitting it returns every status in the window.

        Example: `client.events.list(sport="thoroughbred", country="au", status="open")`
        """
        return self._client._get(
            "/v1/events",
            _event_list_query(
                sport=sport,
                status=status,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            EventPage,
        )

    def iter(
        self,
        *,
        sport: Sequence[Sport] | Sport | None = None,
        status: Sequence[EventStatus] | EventStatus | None = None,
        country: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        event: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        limit: int | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> Iterator[Event]:
        """Walk every page of matching events."""
        after: str | None = None
        while True:
            page = self.list(
                sport=sport,
                status=status,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                after=after,
                limit=limit,
                include=include,
            )
            yield from page
            if not page.next:
                return
            after = page.next

    def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Event:
        """Fetch one event by public id (`evt_...`)."""
        return self._client._get("/v1/events/" + id, list_query(include=include), Event)

    def snapshot(
        self,
        id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> EventSnapshot:
        """Bootstrap one event: card + odds + a stream cursor captured before the read.

        Then `client.follow(snapshot)` to subscribe without a snapshot replay.
        """
        return self._client._get(
            f"/v1/events/{id}/snapshot",
            list_query(source=source, include=include),
            EventSnapshot,
        )


class AsyncEvents:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        sport: Sequence[Sport] | Sport | None = None,
        status: Sequence[EventStatus] | EventStatus | None = None,
        country: Sequence[str] | str | None = None,
        meeting: Sequence[str] | str | None = None,
        event: Sequence[str] | str | None = None,
        venue: Sequence[str] | str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> EventPage:
        return await self._client._aget(
            "/v1/events",
            _event_list_query(
                sport=sport,
                status=status,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                after=after,
                before=before,
                limit=limit,
                include=include,
            ),
            EventPage,
        )

    async def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Event:
        return await self._client._aget("/v1/events/" + id, list_query(include=include), Event)

    async def snapshot(
        self,
        id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> EventSnapshot:
        return await self._client._aget(
            f"/v1/events/{id}/snapshot",
            list_query(source=source, include=include),
            EventSnapshot,
        )
