from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.outcome import Outcome, OutcomePage
from ._pagination import awalk, walk

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Outcomes:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        market: Sequence[str] | str,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> OutcomePage:
        """List outcomes for one market. Example: `client.outcomes.list(market=market_id)`"""
        if not market:
            raise FilterRequiredError(
                "outcomes", "market", "client.outcomes.list(market=market_id)"
            )
        return self._client._get(
            "/v1/outcomes",
            list_query(market=market, after=after, before=before, limit=limit),
            OutcomePage,
        )

    def iter(
        self,
        *,
        market: Sequence[str] | str,
        limit: int | None = None,
    ) -> Iterator[Outcome]:
        """Walk every page of matching outcome rows.

        The cursor goes back to `/v1/outcomes` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        def fetch(after: str | None) -> OutcomePage:
            return self.list(
                market=market,
                limit=limit,
                after=after,
            )

        return walk(fetch)

    def retrieve(self, id: str) -> Outcome:
        return self._client._get("/v1/outcomes/" + id, None, Outcome)


class AsyncOutcomes:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        market: Sequence[str] | str,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> OutcomePage:
        if not market:
            raise FilterRequiredError(
                "outcomes", "market", "client.outcomes.list(market=market_id)"
            )
        return await self._client._aget(
            "/v1/outcomes",
            list_query(market=market, after=after, before=before, limit=limit),
            OutcomePage,
        )

    async def iter(
        self,
        *,
        market: Sequence[str] | str,
        limit: int | None = None,
    ) -> AsyncIterator[Outcome]:
        """Walk every page of matching outcome rows.

        The cursor goes back to `/v1/outcomes` and nowhere else — a cursor
        is only valid on the collection that issued it.
        """

        async def fetch(after: str | None) -> OutcomePage:
            return await self.list(
                market=market,
                limit=limit,
                after=after,
            )

        async for row in awalk(fetch):
            yield row

    async def retrieve(self, id: str) -> Outcome:
        return await self._client._aget("/v1/outcomes/" + id, None, Outcome)
