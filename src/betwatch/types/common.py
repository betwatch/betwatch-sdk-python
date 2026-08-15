from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

import msgspec

T = TypeVar("T")


class Model(msgspec.Struct, omit_defaults=True, kw_only=True, rename="camel"):
    """Wire object: snake_case attributes, camelCase JSON."""

    def to_dict(self) -> dict[str, Any]:
        value = msgspec.to_builtins(self)
        if not isinstance(value, dict):
            raise TypeError("to_dict expected a struct")
        return value

    def to_json(self) -> bytes:
        return msgspec.json.encode(self)


def to_dict(value: Any) -> Any:
    """JSON-ready builtins. Safe for pandas / json.dumps via default=str."""
    return msgspec.to_builtins(value)


def to_json(value: Any) -> bytes:
    return msgspec.json.encode(value)


def to_records(items: Any) -> list[dict[str, Any]]:
    """Rows for `pandas.DataFrame.from_records(...)`."""
    value = msgspec.to_builtins(items)
    if value is None:
        return []
    if isinstance(value, list):
        return [row if isinstance(row, dict) else {"value": row} for row in value]
    if isinstance(value, dict):
        return [value]
    return [{"value": value}]


def as_sequence(value: Sequence[str] | str | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return [item for item in value if item is not None]


class Money(Model):
    amount_cents: int
    currency: str


class NamedPerson(Model):
    name: str


class Parent(Model):
    name: str
    country: str | None = None
    competitor_id: str | None = None


class Pool(Model):
    country: str
    jurisdiction: str


class PriceLevel(Model):
    price: float
