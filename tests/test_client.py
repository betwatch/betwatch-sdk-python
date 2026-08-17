from __future__ import annotations

from typing import Any, cast

import httpx
import pytest

from betwatch import Betwatch, InternalServerError
from betwatch._base_client import decode_model
from betwatch.types.snapshot import EventSnapshot


def _snapshot(*, source: list[str] | None = None) -> EventSnapshot:
    return decode_model(
        "/v1/events/evt_1/snapshot",
        (
            b'{"stream":{"cursor":"cur_1","event":["evt_1"],"source":'
            + __import__("json").dumps(source or []).encode()
            + b'},"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
            b'"startAt":"2026-08-15T04:00:00Z","status":"open"},"entrants":[],"markets":[],'
            b'"outcomes":[],"odds":[],"coverage":[]}'
        ),
        EventSnapshot,
    )


def test_follow_uses_server_issued_continuation_scope() -> None:
    with Betwatch(api_key="bw_test", base_url="http://localhost:8888") as client:
        stream = client.follow(_snapshot(source=["sportsbet"]))

    assert stream.cursor == "cur_1"
    assert stream._params["event"] == ["evt_1"]
    assert stream._params["source"] == ["sportsbet"]
    assert stream._params["snapshot"] == "none"


def test_snapshot_rejects_missing_or_empty_continuation_cursor() -> None:
    body = (
        b'{"stream":{"cursor":"","event":["evt_1"],"source":[]},'
        b'"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-15T04:00:00Z","status":"open"}}'
    )
    with pytest.raises(Exception, match="stream.cursor must be non-empty"):
        decode_model("/v1/events/evt_1/snapshot", body, EventSnapshot)


def test_rest_retries_are_bounded_and_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(503, content=b'{"detail":"down"}'),
        httpx.Response(503, content=b'{"detail":"down"}'),
        httpx.Response(200, content=b'{"items":[]}'),
    ]

    class FakeRaw:
        def get(self, path: str, *, params: object) -> httpx.Response:
            return responses.pop(0)

        def close(self) -> None:
            return None

    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=2)
    object.__setattr__(client, "_raw", FakeRaw())
    monkeypatch.setattr("betwatch._client.time.sleep", lambda _: None)
    try:
        page = client.sources.list()
        assert not page.items
        assert not responses
    finally:
        client.close()


def test_rest_zero_retries_surfaces_first_status() -> None:
    class FakeRaw:
        def get(self, path: str, *, params: object) -> httpx.Response:
            return httpx.Response(503, content=b'{"code":"stream_unavailable"}')

        def close(self) -> None:
            return None

    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888", max_retries=0)
    object.__setattr__(client, "_raw", FakeRaw())
    try:
        with pytest.raises(InternalServerError):
            client.sources.list()
    finally:
        client.close()


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_max_retries_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError, match="max_retries"):
        Betwatch(api_key="bw_test", max_retries=cast(Any, value))
