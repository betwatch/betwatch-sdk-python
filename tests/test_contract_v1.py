"""Alignment with the public /v2 contract rework.

Covers the parts of the contract the SDK has to encode rather than merely
pass through: the two 429 budgets, the three 403 causes, RFC 9457 members,
budget headers, opaque ids, and collection-scoped cursors.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from betwatch import (
    AccountDisabledError,
    APIStatusError,
    AsyncBetwatch,
    Betwatch,
    EntitlementEmptyError,
    ErrorCodes,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
)


def _problem(status: int, code: str, **extra: Any) -> httpx.Response:
    body = {
        "type": f"https://betwatch.com/problems/{code}",
        "title": code.replace("_", " ").title(),
        "status": status,
        "detail": f"{code} happened",
        "code": code,
        **extra,
    }
    return httpx.Response(
        status,
        content=json.dumps(body).encode(),
        headers=extra.pop("_headers", {}) or {},
    )


class FakeRaw:
    """Stands in for httpx.Client, recording the paths it was asked for."""

    def __init__(self, *responses: httpx.Response) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Any]] = []

    def get(self, path: str, *, params: object) -> httpx.Response:
        self.calls.append((path, params))
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    def close(self) -> None:
        return None


class AsyncFakeRaw:
    """Same, for the async client."""

    def __init__(self, *responses: httpx.Response) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Any]] = []

    async def get(self, path: str, *, params: object) -> httpx.Response:
        self.calls.append((path, params))
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    async def aclose(self) -> None:
        return None


def _client(raw: FakeRaw, *, max_retries: int = 2) -> Betwatch:
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=max_retries)
    object.__setattr__(client, "_raw", raw)
    return client


def _aclient(raw: AsyncFakeRaw) -> AsyncBetwatch:
    client = AsyncBetwatch(api_key="bw_test", base_url="http://localhost:8888")
    object.__setattr__(client, "_raw", raw)
    return client


# --- the two 429 budgets ------------------------------------------------


def test_quota_exceeded_fails_fast_without_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = FakeRaw(_problem(429, ErrorCodes.QUOTA_EXCEEDED))
    slept: list[float] = []
    monkeypatch.setattr("betwatch._client.time.sleep", lambda s: slept.append(s))
    client = _client(raw, max_retries=3)
    try:
        with pytest.raises(QuotaExceededError):
            client.sources.list()
    finally:
        client.close()
    assert len(raw.calls) == 1, "monthly quota does not refill inside a retry budget"
    assert not slept


def test_quota_exceeded_is_not_caught_as_a_rate_limit() -> None:
    raw = FakeRaw(_problem(429, ErrorCodes.QUOTA_EXCEEDED))
    client = _client(raw, max_retries=0)
    try:
        with pytest.raises(QuotaExceededError):
            try:
                client.sources.list()
            except RateLimitError:  # pragma: no cover - the bug this guards
                pytest.fail("quota_exceeded must not be swallowed by except RateLimitError")
    finally:
        client.close()


def test_rate_limited_retries_and_honours_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    limited = _problem(429, ErrorCodes.RATE_LIMITED)
    limited.headers["Retry-After"] = "3"
    raw = FakeRaw(limited, httpx.Response(200, content=b'{"items":[]}'))
    slept: list[float] = []
    monkeypatch.setattr("betwatch._client.time.sleep", lambda s: slept.append(s))
    client = _client(raw, max_retries=2)
    try:
        assert not client.sources.list().items
    finally:
        client.close()
    assert len(raw.calls) == 2
    assert slept == [3.0]


def test_rate_limit_error_exposes_retry_after() -> None:
    limited = _problem(429, ErrorCodes.RATE_LIMITED)
    limited.headers["Retry-After"] = "7"
    client = _client(FakeRaw(limited), max_retries=0)
    try:
        with pytest.raises(RateLimitError) as caught:
            client.sources.list()
    finally:
        client.close()
    assert caught.value.retry_after == 7.0


# --- the three 403 causes -----------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (ErrorCodes.ENTITLEMENT_EMPTY, EntitlementEmptyError),
        (ErrorCodes.ACCOUNT_DISABLED, AccountDisabledError),
        (ErrorCodes.SCOPE_REQUIRED, PermissionDeniedError),
    ],
)
def test_403_causes_get_distinct_types(code: str, expected: type[APIStatusError]) -> None:
    client = _client(FakeRaw(_problem(403, code)), max_retries=0)
    try:
        with pytest.raises(expected) as caught:
            client.sources.list()
    finally:
        client.close()
    assert caught.value.code == code
    assert isinstance(caught.value, PermissionDeniedError)


def test_entitlement_empty_is_not_an_empty_page() -> None:
    """It used to be indistinguishable from a quiet raceday. It must not be."""
    client = _client(FakeRaw(_problem(403, ErrorCodes.ENTITLEMENT_EMPTY)), max_retries=0)
    try:
        with pytest.raises(EntitlementEmptyError):
            client.sources.list()
    finally:
        client.close()


# --- RFC 9457 members ----------------------------------------------------


def test_problem_field_errors_and_instance_are_parsed() -> None:
    response = _problem(
        422,
        ErrorCodes.INVALID_REQUEST,
        instance="/v2/events",
        errors=[
            {"message": "must be <= 200", "location": "query.limit", "value": 5000},
            {"message": "unknown sport", "location": "query.sport", "value": "camel"},
        ],
    )
    client = _client(FakeRaw(response), max_retries=0)
    try:
        with pytest.raises(APIStatusError) as caught:
            client.sources.list()
    finally:
        client.close()
    err = caught.value
    assert err.instance == "/v2/events"
    assert err.type is not None and err.type.endswith("invalid_request")
    assert [e.location for e in err.errors] == ["query.limit", "query.sport"]
    assert err.errors[0].value == 5000
    assert "query.limit: must be <= 200" in str(err)


def test_support_ids_appear_in_str_and_repr() -> None:
    response = _problem(500, ErrorCodes.INTERNAL_ERROR)
    response.headers["x-request-id"] = "req_abc"
    response.headers["x-trace-id"] = "trc_def"
    client = _client(FakeRaw(response), max_retries=0)
    try:
        with pytest.raises(APIStatusError) as caught:
            client.sources.list()
    finally:
        client.close()
    rendered = str(caught.value) + repr(caught.value)
    assert "req_abc" in rendered
    assert "trc_def" in rendered


def test_unknown_problem_code_still_raises_by_status() -> None:
    """The contract only grows; a code we have never seen must not break."""
    client = _client(FakeRaw(_problem(403, "a_code_from_the_future")), max_retries=0)
    try:
        with pytest.raises(PermissionDeniedError) as caught:
            client.sources.list()
    finally:
        client.close()
    assert caught.value.code == "a_code_from_the_future"


# --- budget headers ------------------------------------------------------


def test_rate_limit_headers_are_surfaced_on_success_and_error() -> None:
    ok = httpx.Response(
        200,
        content=b'{"items":[]}',
        headers={
            "x-ratelimit-limit": "120",
            "x-ratelimit-remaining": "119",
            "x-ratelimit-reset": "41",
            "x-ratelimit-monthly-limit": "100000",
            "x-ratelimit-monthly-remaining": "42",
        },
    )
    client = _client(FakeRaw(ok), max_retries=0)
    try:
        client.sources.list()
        assert client.rate_limit is not None
        assert client.rate_limit.limit == 120
        assert client.rate_limit.remaining == 119
        assert client.rate_limit.monthly_remaining == 42
    finally:
        client.close()

    spent = _problem(429, ErrorCodes.QUOTA_EXCEEDED)
    spent.headers["x-ratelimit-monthly-remaining"] = "0"
    client = _client(FakeRaw(spent), max_retries=0)
    try:
        with pytest.raises(QuotaExceededError) as caught:
            client.sources.list()
    finally:
        client.close()
    assert caught.value.rate_limit is not None
    assert caught.value.rate_limit.monthly_remaining == 0


def test_missing_budget_headers_leave_rate_limit_unset() -> None:
    client = _client(FakeRaw(httpx.Response(200, content=b'{"items":[]}')), max_retries=0)
    try:
        client.sources.list()
        assert client.rate_limit is None
    finally:
        client.close()


# --- opaque ids and unknown fields --------------------------------------


def test_dotted_derived_id_reaches_the_path_untouched() -> None:
    raw = FakeRaw(
        httpx.Response(
            200,
            content=b'{"$schema":"https://x/Odds.json","id":"odd_7Yz.4mQ",'
            b'"eventId":"evt_1","key":"win",'
            b'"source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},"state":"available","price":3.4}',
        )
    )
    client = _client(raw, max_retries=0)
    try:
        odds = client.odds.retrieve("odd_7Yz.4mQ")
    finally:
        client.close()
    assert raw.calls[0][0] == "/v2/odds/odd_7Yz.4mQ"
    assert odds.id == "odd_7Yz.4mQ"


def test_schema_member_and_future_fields_are_ignored() -> None:
    client = _client(
        FakeRaw(
            httpx.Response(
                200,
                content=b'{"$schema":"https://x/SourcePage.json","items":[],'
                b'"aFieldInventedNextQuarter":{"nested":true}}',
            )
        ),
        max_retries=0,
    )
    try:
        assert not client.sources.list().items
    finally:
        client.close()


# --- collection-scoped cursors ------------------------------------------


async def test_async_iter_feeds_the_cursor_back_to_the_same_collection() -> None:
    pages = [
        httpx.Response(
            200,
            content=b'{"items":[{"id":"evt_1","sport":"thoroughbred","name":"R1",'
            b'"startAt":"2026-08-15T04:00:00Z","status":"open"}],"next":"cur_page2"}',
        ),
        httpx.Response(
            200,
            content=b'{"items":[{"id":"evt_2","sport":"thoroughbred","name":"R2",'
            b'"startAt":"2026-08-15T04:30:00Z","status":"open"}],"next":null}',
        ),
    ]
    raw = AsyncFakeRaw(*pages)
    client = _aclient(raw)
    try:
        seen = [event.id async for event in client.events.iter(sport="thoroughbred")]
    finally:
        await client.close()

    assert seen == ["evt_1", "evt_2"]
    assert [path for path, _ in raw.calls] == ["/v2/events", "/v2/events"]
    second = dict(raw.calls[1][1])
    assert second["after"] == "cur_page2"


# --- redirects the contract does not declare ------------------------------


def test_an_undeclared_redirect_is_named_not_decoded() -> None:
    """Merged entities write a PublicRedirect; /v2 declares no 3xx.

    Before this, a redirect reached the decoder and surfaced as "Input data was
    truncated" — an error that says nothing about what happened. The SDK does
    not follow it: httpx strips `Authorization` across origins but not custom
    headers, so following would forward `X-API-Key` wherever Location points.
    """
    from betwatch import UnexpectedRedirectError

    redirecting = FakeRaw(httpx.Response(308, headers={"Location": "/v2/entrants/ent_new"}))
    client = _client(redirecting, max_retries=0)
    try:
        with pytest.raises(UnexpectedRedirectError) as caught:
            client.entrants.retrieve("ent_old")
    finally:
        client.close()
    assert caught.value.status_code == 308
    assert caught.value.location == "/v2/entrants/ent_new"
    assert "does not follow" in str(caught.value)


def test_the_contract_still_declares_no_redirect() -> None:
    """If a 3xx appears in the contract, the SDK needs a decision, not an error."""
    import json
    from pathlib import Path

    spec = json.loads((Path(__file__).parent / "contract" / "openapi.json").read_text())
    declared = {
        status
        for item in spec["paths"].values()
        for method, op in item.items()
        if method == "get"
        for status in op["responses"]
    }
    assert not [s for s in declared if s.startswith("3")], (
        "the contract now declares a redirect — decide whether to follow it"
    )


def test_a_derived_id_lost_to_a_merge_is_a_plain_not_found() -> None:
    """Stored ids survive a merge; derived ids do not, and that is not a bug.

    `mkt_`, `out_` and `odd_` embed their owning event, so after a merge the
    same market has a different id. The correct client response is to re-read
    the event, so this must surface as an ordinary NotFoundError rather than
    anything that invites special handling.
    """
    from betwatch import NotFoundError

    client = _client(FakeRaw(_problem(404, ErrorCodes.NOT_FOUND)), max_retries=0)
    try:
        with pytest.raises(NotFoundError) as caught:
            client.odds.retrieve("odd_7Yz.4mQ")
    finally:
        client.close()
    assert caught.value.code == ErrorCodes.NOT_FOUND
