from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.enums import EventStatus, IncludeFlag, Sport
from ..types.event import Event, EventPage
from ..types.snapshot import EventSnapshot
from ._pagination import awalk, walk

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

        Sends exactly the filters you pass. With no window the API starts five
        minutes ago, so a bare `limit=5` is the next few races; ask for history
        with `start_from`.

        `status` is the public lifecycle word (`open`, `final`, …). There is
        no default: omitting it returns every status in the window.

        Example: `client.events.list(sport="thoroughbred", country="au", status="open")`
        """
        return self._client._get(
            "/v2/events",
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
        """Walk every page of matching events.

        A cursor belongs to the collection that issued it, so `next` only ever
        goes back to `/v2/events`.
        """

        def fetch(after: str | None) -> EventPage:
            return self.list(
                sport=sport,
                status=status,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                limit=limit,
                include=include,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Event:
        """Fetch one event by public id (`evt_...`)."""
        return self._client._get("/v2/events/" + id, list_query(include=include), Event)

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
            f"/v2/events/{id}/snapshot",
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
            "/v2/events",
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

    async def iter(
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
    ) -> AsyncIterator[Event]:
        """Walk every page of matching events.

        A cursor belongs to the collection that issued it, so `next` only ever
        goes back to `/v2/events`.
        """

        async def fetch(after: str | None) -> EventPage:
            return await self.list(
                sport=sport,
                status=status,
                country=country,
                meeting=meeting,
                event=event,
                venue=venue,
                start_from=start_from,
                start_to=start_to,
                limit=limit,
                include=include,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str, *, include: Sequence[str] | str | None = None) -> Event:
        return await self._client._aget("/v2/events/" + id, list_query(include=include), Event)

    async def snapshot(
        self,
        id: str,
        *,
        source: Sequence[str] | str | None = None,
        include: Sequence[IncludeFlag] | IncludeFlag | None = None,
    ) -> EventSnapshot:
        """Bootstrap one event: card + odds + a stream cursor captured before the read.

        Then `client.follow(snapshot)` to subscribe without a snapshot replay.

        `include="history"` fills each `Odds.history` with that source's
        fluctuations. It is honoured here as of contract 1.0.0 — it was
        previously accepted and ignored — and doubles what the call costs
        against your monthly quota, exactly like the equivalent `/v2/odds`
        read. Ask for it only when you use it.
        """
        return await self._client._aget(
            f"/v2/events/{id}/snapshot",
            list_query(source=source, include=include),
            EventSnapshot,
        )
