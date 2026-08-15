from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

import httpx
import msgspec

from .__about__ import __version__
from ._exceptions import APIDecodeError, APIKeyNotSetError, error_for_status

_T = TypeVar("_T")

DEFAULT_BASE_URL = "https://api-beta.betwatch.com"
STREAM_READ_TIMEOUT = 45.0


def require_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("BETWATCH_API_KEY")
    if not key:
        raise APIKeyNotSetError()
    return key


def resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get("BETWATCH_API_URL") or DEFAULT_BASE_URL).rstrip("/")


def flatten(params: Mapping[str, Any]) -> list[tuple[str, str | float | None]]:
    items: list[tuple[str, str | float | None]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if item is not None:
                    items.append((key, str(item)))
        elif isinstance(value, bool):
            items.append((key, "true" if value else "false"))
        else:
            items.append((key, str(value)))
    return items


def safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


_LIST_KEYS = frozenset(
    {
        "items",
        "entrants",
        "markets",
        "outcomes",
        "odds",
        "coverage",
        "history",
        "back",
        "lay",
        "dividends",
        "positions",
        "entrantIds",
    }
)


def _null_lists_to_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ([] if item is None and key in _LIST_KEYS else _null_lists_to_empty(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_null_lists_to_empty(item) for item in value]
    return value


def decode_model(path: str, content: bytes, model: type[_T]) -> _T:
    try:
        raw = msgspec.json.decode(content)
        return msgspec.convert(_null_lists_to_empty(raw), type=model)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        raise APIDecodeError(path, exc) from exc


def default_headers(api_key: str) -> dict[str, str]:
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": f"betwatch-python/{__version__}",
    }


def stream_headers_and_query(
    params: Mapping[str, Any],
    cursor: str | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build stream headers/query. A known cursor always becomes Last-Event-ID.

    Reconnects and REST-bootstrapped follows send snapshot=none so the server
    does not replay a full snapshot.
    """
    headers: dict[str, str] = {"Accept": "text/event-stream"}
    query = dict(params)
    if cursor:
        headers["Last-Event-ID"] = cursor
        query["snapshot"] = "none"
        query.pop("cursor", None)
    return headers, query


def default_event_window() -> tuple[str, str]:
    """Raceday window used when list() is called without start_from/start_to.

    Unscoped /v1/events is oldest-first across the entitlement history, so a
    bare `limit=5` returns last month's card. Examples and agents want today.
    """
    now = datetime.now(UTC)
    start = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    end = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    return start, end


def retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            value = float(raw)
            if 0 < value <= 10:
                return value
        except ValueError:
            pass
    return min(0.4 * (2**attempt), 4.0)


def _header(response: httpx.Response, name: str) -> str | None:
    value = response.headers.get(name)
    return value if value else None


def raise_if_error(response: httpx.Response, path: str) -> None:
    if response.status_code >= 400:
        raise error_for_status(
            response.status_code,
            path=path,
            body=safe_json(response),
            request_id=_header(response, "x-request-id"),
            trace_id=_header(response, "x-trace-id"),
        )


def list_query(
    *,
    sport: Sequence[str] | str | None = None,
    country: Sequence[str] | str | None = None,
    meeting: Sequence[str] | str | None = None,
    event: Sequence[str] | str | None = None,
    venue: Sequence[str] | str | None = None,
    market: Sequence[str] | str | None = None,
    outcome: Sequence[str] | str | None = None,
    entrant: Sequence[str] | str | None = None,
    source: Sequence[str] | str | None = None,
    competitor: Sequence[str] | str | None = None,
    start_from: str | None = None,
    start_to: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int | None = None,
    include: Sequence[str] | str | None = None,
    status: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    from .types.common import as_sequence

    return {
        "sport": as_sequence(sport),
        "status": as_sequence(status),
        "country": as_sequence(country),
        "meeting": as_sequence(meeting),
        "event": as_sequence(event),
        "venue": as_sequence(venue),
        "market": as_sequence(market),
        "outcome": as_sequence(outcome),
        "entrant": as_sequence(entrant),
        "source": as_sequence(source),
        "competitor": as_sequence(competitor),
        "startFrom": start_from,
        "startTo": start_to,
        "after": after,
        "before": before,
        "limit": limit,
        "include": as_sequence(include),
    }
