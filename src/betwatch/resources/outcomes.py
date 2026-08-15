from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from .._exceptions import FilterRequiredError
from ..types.outcome import Outcome, OutcomePage

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

    async def retrieve(self, id: str) -> Outcome:
        return await self._client._aget("/v1/outcomes/" + id, None, Outcome)
