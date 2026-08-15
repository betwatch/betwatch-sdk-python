from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Generic, TypeVar

from .common import Model, to_records
from .coverage import Coverage

T = TypeVar("T")


class Page(Model, Generic[T]):
    """One list page. Iterate it to walk `items`. Follow `next` with after=."""

    items: list[T] = []
    next: str | None = None
    previous: str | None = None
    cursor: str | None = None
    coverage: list[Coverage] | None = None

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> T:
        return self.items[index]

    def to_records(self) -> list[dict[str, Any]]:
        return to_records(self.items)
