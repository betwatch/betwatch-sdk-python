from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from random import random
from time import time
from typing import Any, TypeVar

import httpx
import msgspec

from .__about__ import __version__
from ._compat import unknown_value_coercer
from ._exceptions import (
    APIDecodeError,
    APIKeyNotSetError,
    CredentialInQueryError,
    error_for_status,
    is_retryable_code,
)
from ._ratelimit import RateLimit
from .types.enums import BudgetHeaders

_T = TypeVar("_T")

DEFAULT_BASE_URL = "https://api-beta.betwatch.com"
DEFAULT_MAX_RETRIES = 2
# A `snapshot=full` bootstrap can send nothing for 45s or more while the server
# hydrates — measured 23s, 35s and 46s of complete silence on a broad scope — so
# a 45s read timeout aborted healthy streams and restarted them from zero. This
# only has to outlast the silent window; keepalives arrive every ~15s once the
# server is emitting them.
STREAM_READ_TIMEOUT = 120.0
_MAX_RETRY_DELAY = 8.0
_MAX_RETRY_AFTER = 60.0
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def require_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("BETWATCH_API_KEY")
    if not key:
        raise APIKeyNotSetError()
    return key


def resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get("BETWATCH_API_URL") or DEFAULT_BASE_URL).rstrip("/")


def flatten(params: Mapping[str, Any]) -> list[tuple[str, str | float | None]]:
    reject_credential_params(params)
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
        raw = _null_lists_to_empty(msgspec.json.decode(content))
        coerce = unknown_value_coercer(model)
        if coerce is not None:
            raw = coerce(raw)
        return msgspec.convert(raw, type=model)
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


def parse_retry_after(response: httpx.Response) -> float | None:
    """The server's Retry-After in seconds, exactly as sent.

    Deliberately unbounded. On `quota_exceeded` the contract points this at the
    monthly reset, which can be weeks out — that is worth reporting to a caller
    deciding when to resume, even though nothing should ever sleep on it.
    """
    raw = response.headers.get(BudgetHeaders.RETRY_AFTER)
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        try:
            value = parsedate_to_datetime(raw).timestamp() - time()
        except (TypeError, ValueError, OverflowError):
            return None
    return value if value > 0 else None


def retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """How long to actually wait before the next attempt, always bounded."""
    value = parse_retry_after(response)
    if value is not None and value <= _MAX_RETRY_AFTER:
        return value
    delay = min(0.5 * (2**attempt), _MAX_RETRY_DELAY)
    return delay * (1 - 0.25 * random())


def problem_code(response: httpx.Response) -> str | None:
    body = safe_json(response)
    if isinstance(body, dict):
        code = body.get("code")
        if isinstance(code, str):
            return code
    return None


def should_retry_status(response: httpx.Response) -> bool:
    """Retry on the problem `code`, falling back to the status.

    The status alone cannot decide this. 429 is `rate_limited` (wait it out),
    `quota_exceeded` (weeks away — fail fast) and `stream_limit` (close a
    connection instead); 409 is a cursor that needs a REST re-bootstrap rather
    than the same request again.
    """
    directive = response.headers.get("x-should-retry")
    if directive == "true":
        return True
    if directive == "false":
        return False
    by_code = is_retryable_code(problem_code(response))
    if by_code is not None:
        return by_code
    return response.status_code in _RETRYABLE_STATUS or response.status_code >= 500


# Anything the server would read as a credential in the query string. It
# refuses these with 401 even when the header is also present, so the SDK
# refuses to build such a URL at all rather than emitting a request that
# cannot succeed.
_CREDENTIAL_PARAMS = frozenset({"apikey", "api_key", "key", "token", "access_token"})


def reject_credential_params(params: Mapping[str, Any]) -> None:
    offending = sorted(name for name in params if name.lower() in _CREDENTIAL_PARAMS)
    if offending:
        raise CredentialInQueryError(offending)


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
            retry_after=parse_retry_after(response),
            rate_limit=RateLimit.from_headers(response.headers),
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
