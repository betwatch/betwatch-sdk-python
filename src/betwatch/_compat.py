"""Forward compatibility for a contract that only grows.

New fields are already free — the response models do not forbid unknown keys.
New *vocabulary values* are not: a Literal rejects what it has never seen, so
the first time the API adds a sport or an odds state every decode would fail.

This walks a model's type tree once and builds a coercion that rewrites an
unrecognised value to `"unknown"`, which every response-side vocabulary
carries for exactly this purpose. A caller sees `"unknown"` and can decide;
nobody sees a decode error over a value that is merely newer than the SDK.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Any

import msgspec.inspect as mi

Coercer = Callable[[Any], Any]

_UNKNOWN = "unknown"


def _literal(node: mi.LiteralType) -> Coercer | None:
    values = set(node.values)
    if _UNKNOWN not in values:
        # A request-side vocabulary, or one with no room for a new value.
        # Leave it strict: the caller sent it, so a bad value is their bug.
        return None

    def coerce(value: Any) -> Any:
        if isinstance(value, str) and value not in values:
            return _UNKNOWN
        return value

    return coerce


def _sequence(inner: Coercer) -> Coercer:
    def coerce(value: Any) -> Any:
        return [inner(item) for item in value] if isinstance(value, list) else value

    return coerce


def _mapping(inner: Coercer) -> Coercer:
    def coerce(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: inner(item) for key, item in value.items()}
        return value

    return coerce


def _union(parts: list[Coercer]) -> Coercer:
    def coerce(value: Any) -> Any:
        for part in parts:
            value = part(value)
        return value

    return coerce


def _struct(fields: dict[str, Coercer]) -> Coercer:
    def coerce(value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {key: fields[key](item) if key in fields else item for key, item in value.items()}

    return coerce


def _build(node: mi.Type, seen: frozenset[type]) -> Coercer | None:
    if isinstance(node, mi.LiteralType):
        return _literal(node)
    if isinstance(node, (mi.ListType, mi.SetType, mi.VarTupleType)):
        inner = _build(node.item_type, seen)
        return _sequence(inner) if inner else None
    if isinstance(node, mi.DictType):
        inner = _build(node.value_type, seen)
        return _mapping(inner) if inner else None
    if isinstance(node, mi.UnionType):
        parts = [built for built in (_build(part, seen) for part in node.types) if built]
        return _union(parts) if parts else None
    if isinstance(node, mi.StructType):
        if node.cls in seen:  # self-referential model; stop recursing
            return None
        nested = seen | {node.cls}
        fields = {}
        for field in node.fields:
            built = _build(field.type, nested)
            if built is not None:
                fields[field.encode_name] = built
        return _struct(fields) if fields else None
    return None


@cache
def unknown_value_coercer(model: type) -> Coercer | None:
    """A coercion for `model`, or None when it has no closed vocabularies."""
    try:
        return _build(mi.type_info(model), frozenset())
    except (TypeError, NotImplementedError):  # pragma: no cover - exotic annotation
        return None
