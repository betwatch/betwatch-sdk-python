from __future__ import annotations

from typing import TYPE_CHECKING

from ..types.competitor import Competitor

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Competitors:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def retrieve(self, id: str) -> Competitor:
        return self._client._get("/v1/competitors/" + id, None, Competitor)


class AsyncCompetitors:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def retrieve(self, id: str) -> Competitor:
        return await self._client._aget("/v1/competitors/" + id, None, Competitor)
