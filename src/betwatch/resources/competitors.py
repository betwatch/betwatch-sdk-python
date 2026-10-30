from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.competitor import Competitor, CompetitorForm, CompetitorRun
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Competitors:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def retrieve(self, id: str) -> Competitor:
        return self._client._get("/v2/competitors/" + id, None, Competitor)

    def form(
        self,
        id: str,
        *,
        limit: int | None = None,
        after: str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> CompetitorForm:
        """Known past starts, newest first; defaults to 10. Unknown facts stay None."""
        return self._client._get(
            f"/v2/competitors/{id}/form",
            list_query(limit=limit, after=after, start_from=start_from, start_to=start_to),
            CompetitorForm,
        )

    def iter_form(
        self,
        id: str,
        *,
        limit: int | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> Iterator[CompetitorRun]:
        return walk(
            lambda after: self.form(
                id, limit=limit, after=after, start_from=start_from, start_to=start_to
            )
        )


class AsyncCompetitors:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def retrieve(self, id: str) -> Competitor:
        return await self._client._aget("/v2/competitors/" + id, None, Competitor)

    async def form(
        self,
        id: str,
        *,
        limit: int | None = None,
        after: str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> CompetitorForm:
        return await self._client._aget(
            f"/v2/competitors/{id}/form",
            list_query(limit=limit, after=after, start_from=start_from, start_to=start_to),
            CompetitorForm,
        )

    async def iter_form(
        self,
        id: str,
        *,
        limit: int | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> AsyncIterator[CompetitorRun]:
        async def fetch(after: str | None) -> CompetitorForm:
            return await self.form(
                id, limit=limit, after=after, start_from=start_from, start_to=start_to
            )

        async for run in awalk(fetch):
            yield run
