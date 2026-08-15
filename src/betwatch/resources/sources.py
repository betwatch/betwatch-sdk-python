from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .._base_client import list_query
from ..types.source import SourcePage

if TYPE_CHECKING:
    from .._client import AsyncBetwatch, Betwatch


class Sources:
    def __init__(self, client: Betwatch) -> None:
        self._client = client

    def list(
        self,
        *,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> SourcePage:
        return self._client._get(
            "/v1/sources",
            list_query(after=after, before=before, limit=limit, source=source),
            SourcePage,
        )


class AsyncSources:
    def __init__(self, client: AsyncBetwatch) -> None:
        self._client = client

    async def list(
        self,
        *,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        source: Sequence[str] | str | None = None,
    ) -> SourcePage:
        return await self._client._aget(
            "/v1/sources",
            list_query(after=after, before=before, limit=limit, source=source),
            SourcePage,
        )
