"""The SDK, checked against the published contract itself.

`tests/contract/openapi.json` is a committed copy of the served spec, refreshed
with `uv run tests/contract/sync_openapi.py`. Everything the SDK hardcodes about the
contract — the error-code vocabulary, the budget headers, the operation set —
is asserted against it here, so a contract change fails a test instead of
quietly drifting out of the exception hierarchy.

The contract only *grows*: new codes and new fields may appear. These tests
therefore check that the SDK knows every code the spec declares, not that the
spec declares only codes the SDK knows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from betwatch import BudgetHeaders, ErrorCodes
from betwatch._exceptions import (
    _RETRYABLE_CODES,
    _TERMINAL_CODES,
    APIStatusError,
    error_class_for,
    is_retryable_code,
)
from betwatch._ratelimit import RateLimit

SPEC_PATH = Path(__file__).parent / "contract" / "openapi.json"


@pytest.fixture(scope="session")
def spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text())


def _sdk_codes() -> set[str]:
    return {
        value
        for name, value in vars(ErrorCodes).items()
        if not name.startswith("_") and isinstance(value, str)
    }


# --- the error-code vocabulary -------------------------------------------


def test_sdk_knows_every_code_the_contract_declares(spec: dict[str, Any]) -> None:
    declared = set(spec["components"]["schemas"]["PublicProblem"]["properties"]["code"]["enum"])
    assert declared, "the spec must carry the code enum"
    assert declared <= _sdk_codes(), (
        f"codes missing from ErrorCodes: {sorted(declared - _sdk_codes())}"
    )


def test_error_codes_are_declared_in_contract_order(spec: dict[str, Any]) -> None:
    """ErrorCodes should read as the contract does, not in arrival order."""
    declared = spec["components"]["schemas"]["PublicProblem"]["properties"]["code"]["enum"]
    sdk_order = [
        value
        for name, value in vars(ErrorCodes).items()
        if not name.startswith("_") and isinstance(value, str)
    ]
    assert sdk_order == declared


def test_sdk_invents_no_codes_of_its_own(spec: dict[str, Any]) -> None:
    declared = set(spec["components"]["schemas"]["PublicProblem"]["properties"]["code"]["enum"])
    assert _sdk_codes() <= declared, f"not in the contract: {sorted(_sdk_codes() - declared)}"


def test_every_declared_code_has_a_retry_decision(spec: dict[str, Any]) -> None:
    """No code may be left to the status fallback — that is what the split is for."""
    declared = set(spec["components"]["schemas"]["PublicProblem"]["properties"]["code"]["enum"])
    unclassified = {code for code in declared if is_retryable_code(code) is None}
    assert not unclassified, f"no retry decision for: {sorted(unclassified)}"


def test_retry_classes_do_not_overlap() -> None:
    assert not (_RETRYABLE_CODES & _TERMINAL_CODES)


def test_unknown_codes_still_fall_back_to_the_http_class() -> None:
    """The spec says new codes may be added; that must not become an error."""
    assert is_retryable_code("a_code_added_after_this_release") is None
    assert error_class_for(503, "a_code_added_after_this_release").__name__ == (
        "ServiceUnavailableError"
    )
    assert issubclass(error_class_for(418, "also_new"), APIStatusError)


def test_problem_members_the_sdk_reads_are_all_in_the_contract(spec: dict[str, Any]) -> None:
    properties = spec["components"]["schemas"]["PublicProblem"]["properties"]
    for member in ("type", "title", "status", "detail", "code", "instance", "errors"):
        assert member in properties, member
    for member in ("requestId", "traceId"):
        assert member in properties, member
    field = spec["components"]["schemas"]["ProblemFieldError"]["properties"]
    assert {"message", "location", "value"} <= set(field)


# --- the budget headers ---------------------------------------------------


def _declared_headers(spec: dict[str, Any]) -> dict[str, set[str]]:
    by_status: dict[str, set[str]] = {}
    for path in spec["paths"].values():
        for method, op in path.items():
            if method != "get":
                continue
            for status, response in (op.get("responses") or {}).items():
                by_status.setdefault(status, set()).update(response.get("headers") or {})
    return by_status


def _sdk_headers() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(BudgetHeaders).items()
        if not name.startswith("_") and isinstance(value, str)
    }


def test_budget_header_names_match_the_contract(spec: dict[str, Any]) -> None:
    """BudgetHeaders is the SDK's copy of a contract vocabulary; pin it."""
    declared = set().union(*_declared_headers(spec).values())
    assert declared, "the spec must declare the budget headers"
    known = set(_sdk_headers().values())
    assert declared == known, (
        f"missing from BudgetHeaders: {sorted(declared - known)}, "
        f"not in the contract: {sorted(known - declared)}"
    )


def test_every_declared_header_reaches_a_rate_limit_field(spec: dict[str, Any]) -> None:
    """No declared budget header may be parsed into nowhere."""
    declared = set().union(*_declared_headers(spec).values()) - {BudgetHeaders.RETRY_AFTER}

    limits = RateLimit.from_headers(
        httpx.Headers(
            {
                BudgetHeaders.LIMIT: "300",
                BudgetHeaders.REMAINING: "299",
                BudgetHeaders.RESET: "41",
                BudgetHeaders.MONTHLY_LIMIT: "100000",
                BudgetHeaders.MONTHLY_USED: "58",
                BudgetHeaders.MONTHLY_REMAINING: "99942",
                BudgetHeaders.MONTHLY_RESET: "2026-09-01T00:00:00Z",
            }
        )
    )
    assert limits is not None
    parsed = {
        BudgetHeaders.LIMIT: limits.limit,
        BudgetHeaders.REMAINING: limits.remaining,
        BudgetHeaders.RESET: limits.reset,
        BudgetHeaders.MONTHLY_LIMIT: limits.monthly_limit,
        BudgetHeaders.MONTHLY_USED: limits.monthly_used,
        BudgetHeaders.MONTHLY_REMAINING: limits.monthly_remaining,
        BudgetHeaders.MONTHLY_RESET: limits.monthly_reset,
    }
    assert declared == set(parsed), f"unhandled: {sorted(declared - set(parsed))}"
    assert all(value is not None for value in parsed.values())
    assert limits.monthly_reset is not None and limits.monthly_reset.month == 9


def test_header_types_match_the_contract(spec: dict[str, Any]) -> None:
    """Monthly-Reset is an RFC 3339 instant; the rest are integers."""
    headers = spec["paths"]["/odds"]["get"]["responses"]["429"]["headers"]
    assert headers["X-RateLimit-Monthly-Reset"]["schema"]["format"] == "date-time"
    for name in ("X-RateLimit-Limit", "X-RateLimit-Reset", "X-RateLimit-Monthly-Used"):
        assert headers[name]["schema"]["type"] == "integer", name


def test_retry_after_is_declared_where_the_sdk_expects_it(spec: dict[str, Any]) -> None:
    by_status = _declared_headers(spec)
    assert "Retry-After" in by_status["429"]
    assert "Retry-After" in by_status["503"]


def test_quota_exceeded_retry_after_is_surfaced_but_never_slept_on() -> None:
    """The contract points Retry-After at the monthly reset on quota_exceeded.

    Reporting it is useful; sleeping it is the fortnight-long hot loop the two
    codes exist to prevent.
    """
    from betwatch._base_client import (
        parse_retry_after,
        retry_after_seconds,
        should_retry_status,
    )

    month = httpx.Response(
        429,
        content=json.dumps(
            {
                "type": "x",
                "title": "t",
                "status": 429,
                "detail": "d",
                "code": ErrorCodes.QUOTA_EXCEEDED,
            }
        ).encode(),
        headers={"Retry-After": "1209600"},
    )
    assert parse_retry_after(month) == 1209600.0, "the caller sees the real reset distance"
    assert should_retry_status(month) is False, "but the client never waits it out"
    assert retry_after_seconds(month, 0) <= 8.0, "and no sleep is ever that long"


# --- operation coverage ---------------------------------------------------


def test_published_servers_url_is_the_v2_origin(spec: dict[str, Any]) -> None:
    urls = [server.get("url", "") for server in spec.get("servers") or []]
    assert any(url.rstrip("/").endswith("/v2") for url in urls), urls
    assert "/events" in spec["paths"]
    assert "/v2/events" not in spec["paths"]
    assert "/markets" not in spec["paths"]
    assert "/outcomes" not in spec["paths"]


def test_sdk_covers_every_operation_in_the_contract(spec: dict[str, Any]) -> None:
    from test_contract_surface import OPERATIONS

    declared = {
        op["operationId"]
        for path in spec["paths"].values()
        for method, op in path.items()
        if method == "get" and op.get("operationId")
    }
    covered = set(OPERATIONS) | {"streamRacing"}
    assert declared == covered, (
        f"missing: {sorted(declared - covered)}, stale: {sorted(covered - declared)}"
    )


def test_no_collection_can_be_read_unscoped(spec: dict[str, Any]) -> None:
    """The scoped collections refuse locally, before any request."""
    from betwatch import Betwatch, FilterRequiredError

    client = Betwatch(api_key="bw_test")
    try:
        for resource in ("odds", "entrants"):
            with pytest.raises(FilterRequiredError):
                getattr(client, resource).list()
    finally:
        client.close()


# --- drift ----------------------------------------------------------------


def test_vendored_spec_matches_the_published_one() -> None:
    """Local-only: skipped wherever the API repo is not checked out."""
    import os

    source = Path(
        os.environ.get(
            "BETWATCH_OPENAPI", Path.home() / "Projects/betwatch/apps/docs/public/api/openapi.json"
        )
    )
    if not source.is_file():
        pytest.skip(f"no published spec at {source}")
    assert source.read_bytes() == SPEC_PATH.read_bytes(), (
        "vendored contract is stale — run: uv run tests/contract/sync_openapi.py"
    )


def test_snapshot_forwards_include_history(spec: dict[str, Any]) -> None:
    """include=history is honoured by the snapshot as of 1.0.0, so it must reach the wire."""
    declared = {
        p["name"] for p in spec["paths"]["/events/{id}/snapshot"]["get"].get("parameters", [])
    }
    assert "include" in declared

    from betwatch import Betwatch

    class Raw:
        def __init__(self) -> None:
            self.params: Any = None

        def get(self, path: str, *, params: Any) -> httpx.Response:
            self.params = params
            return httpx.Response(
                200,
                content=b'{"stream":{"cursor":"cur_1","event":["evt_1"],"source":[]},'
                b'"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
                b'"startAt":"2026-08-15T04:00:00Z","status":"open"},"entrants":[],'
                b'"odds":[],"coverage":[]}',
            )

        def close(self) -> None:
            return None

    raw = Raw()
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=0)
    object.__setattr__(client, "_raw", raw)
    try:
        client.events.snapshot("evt_1", include="history")
    finally:
        client.close()
    assert ("include", "history") in raw.params


def test_odds_history_decodes_when_requested() -> None:
    from betwatch._base_client import decode_model
    from betwatch.types.odds import Odds

    odds = decode_model(
        "/v2/odds/odd_1.a",
        b'{"id":"odd_1.a","eventId":"evt_1","key":"win",'
        b'"source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},'
        b'"state":"available","price":3.4,"history":['
        b'{"price":4.0,"updatedAt":"2026-08-17T03:00:00Z"},'
        b'{"price":3.4,"updatedAt":"2026-08-17T04:00:00Z"}]}',
        Odds,
    )
    assert odds.history is not None
    assert [item.price for item in odds.history] == [4.0, 3.4]


# --- stream recovery, pinned to the contract ------------------------------


def test_stream_declares_the_resync_status_the_client_branches_on(
    spec: dict[str, Any],
) -> None:
    """cursor_expired / cursor_scope_changed arrive as 409 on streamRacing."""
    from betwatch._client import RESYNC_CODES, RESYNC_STATUS

    responses = spec["paths"]["/stream"]["get"]["responses"]
    assert str(RESYNC_STATUS) in responses, (
        f"the client treats {RESYNC_STATUS} as resync but the contract does not declare it"
    )
    declared_codes = set(
        spec["components"]["schemas"]["PublicProblem"]["properties"]["code"]["enum"]
    )
    assert RESYNC_CODES <= declared_codes


def test_stream_declares_every_status_the_client_can_meet(spec: dict[str, Any]) -> None:
    responses = set(spec["paths"]["/stream"]["get"]["responses"])
    assert {"401", "403", "409", "422", "429", "503"} <= responses


@pytest.mark.parametrize("status", ["400", "405", "406", "415"])
def test_rest_declares_the_statuses_the_sdk_maps(spec: dict[str, Any], status: str) -> None:
    """Each of these resolves to an exception type, so it must be reachable."""
    from betwatch._exceptions import _STATUS_ERRORS

    rest = [
        op["responses"]
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method == "get" and path != "/stream"
    ]
    assert all(status in responses for responses in rest), status
    assert int(status) in _STATUS_ERRORS, f"nothing maps {status}"


def test_every_declared_status_resolves_to_an_exception(spec: dict[str, Any]) -> None:
    """No status the contract admits to may fall through to a bare APIStatusError."""
    from betwatch._exceptions import APIStatusError, error_class_for

    declared = {
        status
        for item in spec["paths"].values()
        for method, op in item.items()
        if method == "get"
        for status in op["responses"]
        if status.isdigit() and int(status) >= 400
    }
    unmapped = {
        status for status in declared if error_class_for(int(status), None) is APIStatusError
    }
    assert not unmapped, f"no exception type for: {sorted(unmapped)}"


def test_all_error_responses_use_the_one_problem_schema(spec: dict[str, Any]) -> None:
    """One shape everywhere is what lets a single handler cover the API."""
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method != "get":
                continue
            for status, response in op["responses"].items():
                if not status.isdigit() or int(status) < 400:
                    continue
                content = response.get("content") or {}
                schema = content.get("application/problem+json", {}).get("schema", {})
                assert schema.get("$ref", "").endswith("PublicProblem"), (
                    f"{method.upper()} {path} {status} is not a PublicProblem"
                )


# --- requestId is guaranteed ---------------------------------------------


def test_request_id_is_required_by_the_contract(spec: dict[str, Any]) -> None:
    problem = spec["components"]["schemas"]["PublicProblem"]
    assert "requestId" in problem["required"], "the SDK renders it unconditionally"
    assert "traceId" not in problem["required"], "traceId depends on tracing being on"


def test_request_id_comes_from_the_body_even_without_the_header() -> None:
    from betwatch._exceptions import error_for_status

    err = error_for_status(
        503,
        path="/v2/odds",
        body={
            "type": "x",
            "title": "t",
            "status": 503,
            "detail": "d",
            "code": ErrorCodes.UNAVAILABLE,
            "requestId": "01K3F9QW2H7YB4NPX8VJDT6MRC",
        },
    )
    assert err.request_id == "01K3F9QW2H7YB4NPX8VJDT6MRC"
    assert "01K3F9QW2H7YB4NPX8VJDT6MRC" in str(err)
    assert "01K3F9QW2H7YB4NPX8VJDT6MRC" in repr(err)


def test_a_failure_that_never_reached_the_api_says_so() -> None:
    """A proxy 502 has no request id; the rendering must not imply one."""
    from betwatch._exceptions import NO_REQUEST_ID, error_for_status

    err = error_for_status(502, path="/v2/odds", body="<html>bad gateway</html>")
    assert err.request_id is None
    assert NO_REQUEST_ID in str(err)


# --- the scope snapshot ---------------------------------------------------


def test_scope_snapshot_carries_state_and_the_handoff(spec: dict[str, Any]) -> None:
    """One call must return the card, the prices, and the cursor to follow them."""
    ref = spec["paths"]["/events/snapshot"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].split("/")[-1]
    schema = spec["components"]["schemas"][ref]
    assert {"events", "entrants", "odds", "coverage", "stream"} <= set(schema["required"]), (
        "a bootstrap missing prices is what made watch_scope wrong"
    )


def test_sdk_reads_every_filter_the_continuation_carries(spec: dict[str, Any]) -> None:
    """follow() replays these verbatim; a field it drops narrows the scope silently."""
    from betwatch._client import _continuation_params
    from betwatch.types.snapshot import StreamContinuation

    declared = set(spec["components"]["schemas"]["PublicStreamContinuation"]["properties"])
    declared.discard("$schema")
    declared.discard("cursor")  # passed separately, not as a filter

    replayed = set(_continuation_params(StreamContinuation(cursor="cur_1")))
    camel = {
        "".join(w if i == 0 else w.title() for i, w in enumerate(n.split("_"))) for n in replayed
    }
    assert declared <= camel, f"follow() drops: {sorted(declared - camel)}"


def test_a_scope_continuation_needs_no_event_filter() -> None:
    """A scope snapshot is scoped by sport/country, so `event` is legitimately empty."""
    from betwatch.types.snapshot import StreamContinuation

    scoped = StreamContinuation(cursor="cur_1", sport=["thoroughbred"], country=["au"])
    assert scoped.event == []

    with pytest.raises(ValueError, match="cursor"):
        StreamContinuation(cursor="  ")


def test_snapshot_full_is_no_longer_offered_at_scope(spec: dict[str, Any]) -> None:
    """The mode that could not complete is gone; the SDK must not suggest it."""
    description = spec["paths"]["/stream"]["get"].get("description", "")
    assert "/snapshot" in description, "streamRacing should point at the bootstrap"


def test_no_response_array_is_nullable(spec: dict[str, Any]) -> None:
    """Empty collections are `[]`, never null.

    While 36 arrays were declared nullable the SDK walked every decoded payload
    rewriting nulls to empty lists — 0.11ms against msgspec's 0.03ms, 3.5x the
    decode it was protecting. That walk is deleted; this keeps it deleted.
    """
    nullable = [
        f"{name}.{prop}"
        for name, schema in spec["components"]["schemas"].items()
        for prop, definition in (schema.get("properties") or {}).items()
        if isinstance(definition.get("type"), list)
        and "array" in definition["type"]
        and "null" in definition["type"]
    ]
    assert not nullable, f"nullable arrays are back: {nullable}"


def test_the_sdk_no_longer_rewrites_responses_or_queries(spec: dict[str, Any]) -> None:
    """Both compensations are gone; neither should creep back."""
    import inspect

    from betwatch import _base_client
    from betwatch.resources import events

    source = inspect.getsource(_base_client) + inspect.getsource(events)
    assert "_null_lists_to_empty" not in source, "the response walk is back"
    assert "default_event_window" not in source, "the SDK is rewriting queries again"
