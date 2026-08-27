"""Cursor walking, shared by every collection.

A cursor belongs to the collection that issued it: a `next` from `/v2/venues`
is `422 invalid_filter` on `/v2/meetings`. These helpers take the *fetch
function* for one endpoint and feed each cursor back to that same function, so
a cursor cannot reach a different collection by construction.

Cursors are opaque. Nothing here decodes, inspects, or builds one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Protocol, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class _Page(Protocol[T_co]):
    next: str | None

    def __iter__(self) -> Iterator[T_co]: ...


def walk(fetch: Callable[[str | None], _Page[T]]) -> Iterator[T]:
    """Yield every item across pages, following `next` until it stops coming."""
    after: str | None = None
    while True:
        page = fetch(after)
        yield from page
        if not page.next:
            return
        after = page.next


async def awalk(fetch: Callable[[str | None], Awaitable[_Page[T]]]) -> AsyncIterator[T]:
    after: str | None = None
    while True:
        page = await fetch(after)
        for item in page:
            yield item
        if not page.next:
            return
        after = page.next
