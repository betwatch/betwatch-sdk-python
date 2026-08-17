"""The frozen /v1 contract, checked against the SDK surface.

Operation coverage, header-only auth, the full retry table, cursor scoping,
and forward compatibility with values this SDK has never seen.
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
    AuthenticationError,
    Betwatch,
    CredentialInQueryError,
    EntitlementEmptyError,
    ErrorCodes,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServiceUnavailableError,
    StreamLimitError,
    UnprocessableEntityError,
)
from betwatch._base_client import should_retry_status

# --- 1. every operation, named from its operationId ----------------------

# operationId -> the namespaced SDK call that implements it. The SDK groups by
# resource because that is the Python idiom, so `listEvents` is
# `client.events.list`; the mapping is one-to-one and total.
OPERATIONS = {
    "listEvents": ("events", "list"),
    "getEvent": ("events", "retrieve"),
    "getEventSnapshot": ("events", "snapshot"),
    "getSnapshot": ("__client__", "snapshot"),
    "listEntrants": ("entrants", "list"),
    "getEntrant": ("entrants", "retrieve"),
    "getCompetitor": ("competitors", "retrieve"),
    "listMarkets": ("markets", "list"),
    "getMarket": ("markets", "retrieve"),
    "listOutcomes": ("outcomes", "list"),
    "getOutcome": ("outcomes", "retrieve"),
    "listOdds": ("odds", "list"),
    "getOdds": ("odds", "retrieve"),
    "listMeetings": ("meetings", "list"),
    "getMeeting": ("meetings", "retrieve"),
    "listVenues": ("venues", "list"),
    "getVenue": ("venues", "retrieve"),
    "listSources": ("sources", "list"),
}


@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_every_operation_is_implemented(operation: str) -> None:
    resource, method = OPERATIONS[operation]
    for client in (Betwatch(api_key="bw_test"), AsyncBetwatch(api_key="bw_test")):
        target = client if resource == "__client__" else getattr(client, resource)
        assert callable(getattr(target, method)), operation


def test_stream_racing_is_implemented() -> None:
    for client in (Betwatch(api_key="bw_test"), AsyncBetwatch(api_key="bw_test")):
        assert callable(client.stream)
        assert callable(client.watch)
        assert callable(client.follow)


def test_operation_count_matches_the_contract() -> None:
    assert len(OPERATIONS) + 1 == 19, "19 operations: 18 REST plus streamRacing"


def test_every_collection_can_be_paged() -> None:
    client = Betwatch(api_key="bw_test")
    for resource in (
        "events",
        "odds",
        "entrants",
        "markets",
        "outcomes",
        "meetings",
        "venues",
        "sources",
    ):
        assert callable(getattr(client, resource).iter), resource
    client.close()


# --- 2. header-only auth -------------------------------------------------


def test_key_travels_in_the_header_only() -> None:
    client = Betwatch(api_key="bw_secret", base_url="http://localhost:8888")
    try:
        assert client._headers["X-API-Key"] == "bw_secret"
        request = client._raw.build_request("GET", "/v1/events", params=[("sport", "harness")])
        assert "bw_secret" not in str(request.url)
        assert request.headers["X-API-Key"] == "bw_secret"
    finally:
        client.close()


@pytest.mark.parametrize("name", ["apikey", "api_key", "key", "token", "access_token", "API_KEY"])
def test_credential_shaped_query_params_are_refused_locally(name: str) -> None:
    from betwatch._base_client import flatten

    with pytest.raises(CredentialInQueryError) as caught:
        flatten({name: "bw_secret", "sport": "harness"})
    assert name in str(caught.value)


# --- 4. the retry table --------------------------------------------------


def _problem_response(status: int, code: str) -> httpx.Response:
    return httpx.Response(
        status,
        content=json.dumps(
            {"type": f"x#{code}", "title": "t", "status": status, "detail": "d", "code": code}
        ).encode(),
    )


@pytest.mark.parametrize(
    ("code", "status", "retry"),
    [
        (ErrorCodes.RATE_LIMITED, 429, True),
        (ErrorCodes.QUOTA_UNAVAILABLE, 503, True),
        (ErrorCodes.STREAM_UNAVAILABLE, 503, True),
        (ErrorCodes.UNAVAILABLE, 503, True),
        (ErrorCodes.INTERNAL_ERROR, 500, True),
        (ErrorCodes.QUOTA_EXCEEDED, 429, False),
        (ErrorCodes.STREAM_LIMIT, 429, False),
        (ErrorCodes.CURSOR_EXPIRED, 409, False),
        (ErrorCodes.CURSOR_SCOPE_CHANGED, 409, False),
        (ErrorCodes.AUTHENTICATION_REQUIRED, 401, False),
        (ErrorCodes.SCOPE_REQUIRED, 403, False),
        (ErrorCodes.PLAN_REQUIRED, 403, False),
        (ErrorCodes.ENTITLEMENT_EMPTY, 403, False),
        (ErrorCodes.ACCOUNT_DISABLED, 403, False),
        (ErrorCodes.INVALID_REQUEST, 422, False),
        (ErrorCodes.INVALID_FILTER, 422, False),
        (ErrorCodes.FILTER_REQUIRED, 422, False),
        (ErrorCodes.NOT_FOUND, 404, False),
        (ErrorCodes.METHOD_NOT_ALLOWED, 405, False),
        (ErrorCodes.UNSUPPORTED_MEDIA_TYPE, 415, False),
    ],
)
def test_retry_decision_follows_the_published_table(code: str, status: int, retry: bool) -> None:
    assert should_retry_status(_problem_response(status, code)) is retry


@pytest.mark.parametrize(
    ("code", "status", "expected"),
    [
        (ErrorCodes.QUOTA_EXCEEDED, 429, QuotaExceededError),
        (ErrorCodes.STREAM_LIMIT, 429, StreamLimitError),
        (ErrorCodes.RATE_LIMITED, 429, RateLimitError),
        (ErrorCodes.QUOTA_UNAVAILABLE, 503, ServiceUnavailableError),
        (ErrorCodes.STREAM_UNAVAILABLE, 503, ServiceUnavailableError),
        (ErrorCodes.ENTITLEMENT_EMPTY, 403, EntitlementEmptyError),
        (ErrorCodes.ACCOUNT_DISABLED, 403, AccountDisabledError),
        (ErrorCodes.AUTHENTICATION_REQUIRED, 401, AuthenticationError),
        (ErrorCodes.NOT_FOUND, 404, NotFoundError),
        (ErrorCodes.FILTER_REQUIRED, 422, UnprocessableEntityError),
    ],
)
def test_code_selects_the_exception_type(code: str, status: int, expected: type) -> None:
    from betwatch._exceptions import error_class_for

    assert error_class_for(status, code) is expected


def test_unknown_code_falls_back_to_its_http_class() -> None:
    from betwatch._exceptions import error_class_for

    assert error_class_for(404, "invented_next_year") is NotFoundError
    assert error_class_for(418, None) is APIStatusError


# --- 8. forward compatibility --------------------------------------------


def test_unknown_vocabulary_values_read_as_unknown() -> None:
    from betwatch._base_client import decode_model
    from betwatch.types.event import Event

    event = decode_model(
        "/v1/events/evt_1",
        b'{"id":"evt_1","sport":"camel","name":"R1",'
        b'"startAt":"2026-08-15T04:00:00Z","status":"photo_finish"}',
        Event,
    )
    assert event.sport == "unknown"
    assert event.status == "unknown"


def test_known_vocabulary_values_are_untouched() -> None:
    from betwatch._base_client import decode_model
    from betwatch.types.event import Event

    event = decode_model(
        "/v1/events/evt_1",
        b'{"id":"evt_1","sport":"harness","name":"R1",'
        b'"startAt":"2026-08-15T04:00:00Z","status":"final"}',
        Event,
    )
    assert event.sport == "harness"
    assert event.status == "final"


def test_unknown_frame_names_are_no_ops() -> None:
    from betwatch.types.stream import UnknownFrame, frame_for_event

    frame = frame_for_event("weather", "cur_1", {"rain": True})
    assert isinstance(frame, UnknownFrame)
    assert frame.name == "weather"


def test_stream_frame_with_a_new_vocabulary_value_still_decodes() -> None:
    from betwatch.types.stream import OddsFrame, frame_for_event

    frame = frame_for_event(
        "odds",
        "cur_2",
        {
            "id": "odd_7Yz.4mQ",
            "eventId": "evt_1",
            "marketId": "mkt_7Yz.1aB",
            "outcomeId": "out_7Yz.9kL",
            "source": {"id": "sportsbet", "name": "Sportsbet", "kind": "spread_betting"},
            "state": "cashed_out",
            "price": 3.4,
        },
    )
    assert isinstance(frame, OddsFrame)
    assert frame.data.state == "unknown"
    assert frame.data.source.kind == "unknown"


# --- budget headers ------------------------------------------------------


def test_monthly_reset_is_parsed_as_a_timestamp() -> None:
    from betwatch._ratelimit import RateLimit

    limits = RateLimit.from_headers(
        httpx.Headers(
            {
                "x-ratelimit-limit": "120",
                "x-ratelimit-monthly-used": "58",
                "x-ratelimit-monthly-reset": "2026-09-01T00:00:00Z",
            }
        )
    )
    assert limits is not None
    assert limits.limit == 120
    assert limits.monthly_used == 58
    assert limits.monthly_reset is not None
    assert limits.monthly_reset.year == 2026
    assert limits.monthly_reset.month == 9


def test_no_budget_headers_means_no_rate_limit_object() -> None:
    from betwatch._ratelimit import RateLimit

    assert RateLimit.from_headers(httpx.Headers({"content-type": "application/json"})) is None


# --- cursor scoping ------------------------------------------------------


class RecordingRaw:
    def __init__(self, *responses: httpx.Response) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Any]] = []

    def get(self, path: str, *, params: object) -> httpx.Response:
        self.calls.append((path, params))
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    def close(self) -> None:
        return None


def test_pagination_keeps_each_cursor_on_its_own_collection() -> None:
    raw = RecordingRaw(
        httpx.Response(
            200,
            content=b'{"items":[{"id":"ven_1","sport":"thoroughbred","name":"Flemington",'
            b'"country":"AU","timezone":"Australia/Melbourne"}],"next":"lst_venues_p2"}',
        ),
        httpx.Response(
            200,
            content=b'{"items":[{"id":"ven_2","sport":"thoroughbred","name":"Randwick",'
            b'"country":"AU","timezone":"Australia/Sydney"}],"next":null}',
        ),
    )
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=0)
    object.__setattr__(client, "_raw", raw)
    try:
        names = [venue.name for venue in client.venues.iter()]
    finally:
        client.close()

    assert names == ["Flemington", "Randwick"]
    assert {path for path, _ in raw.calls} == {"/v1/venues"}
    assert dict(raw.calls[1][1])["after"] == "lst_venues_p2"


def test_a_foreign_cursor_surfaces_the_servers_rejection() -> None:
    """The SDK never forges a cursor, so a misuse is the server's 422 to make."""
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=0)
    object.__setattr__(
        client, "_raw", RecordingRaw(_problem_response(422, ErrorCodes.INVALID_FILTER))
    )
    try:
        with pytest.raises(UnprocessableEntityError) as caught:
            client.meetings.list(after="lst_a_venues_cursor")
    finally:
        client.close()
    assert caught.value.code == ErrorCodes.INVALID_FILTER
