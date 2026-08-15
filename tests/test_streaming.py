from __future__ import annotations

import pytest

from betwatch import OddsFrame, ResyncRequired
from betwatch._base_client import stream_headers_and_query
from betwatch._streaming import SSEDecoder, frame_from_sse, iter_sse


def test_decoder_parses_named_event_and_keeps_last_event_id() -> None:
    raw = (
        b"id: cur_1\n"
        b"event: ready\n"
        b'data: {"cursor":"cur_1"}\n'
        b"\n"
        b": keepalive\n"
        b"\n"
        b"id: cur_2\n"
        b"event: odds\n"
        b'data: {"id":"odd_1","eventId":"evt_1","marketId":"mkt_1","outcomeId":"out_1",'
        b'"source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},'
        b'"state":"available","price":3.2}\n'
        b"\n"
    )
    events = list(SSEDecoder().iter_bytes(iter([raw[:17], raw[17:40], raw[40:]])))
    named = [event for event in events if event.event]
    assert [event.event for event in named] == ["ready", "odds"]
    assert named[0].id == "cur_1"
    assert named[1].id == "cur_2"
    frame = frame_from_sse(named[1])
    assert isinstance(frame, OddsFrame)
    assert frame.data.price == 3.2
    assert frame.cursor == "cur_2"


def test_odds_set_frame_decodes_live_shaped_rows() -> None:
    raw = (
        b"id: cur_set\n"
        b"event: odds_set\n"
        b'data: {"eventId":"evt_1","marketId":"mkt_1","items":['
        b'{"id":"odd_1","eventId":"evt_1","marketId":"mkt_1","outcomeId":"out_1",'
        b'"source":{"id":"ladbrokes","name":"Ladbrokes","kind":"bookmaker"},'
        b'"state":"available","price":4.2}]}\n'
        b"\n"
    )
    events = list(SSEDecoder().iter_bytes(iter([raw])))
    frame = frame_from_sse(events[0])
    from betwatch import OddsSetFrame
    from betwatch.types.stream import iter_odds

    assert isinstance(frame, OddsSetFrame)
    rows = list(iter_odds(frame))
    assert len(rows) == 1
    assert rows[0].source.id == "ladbrokes"
    assert rows[0].price == 4.2
    assert frame.cursor == "cur_set"


def test_iter_sse_skips_comments_and_frame_policy_skips_ping() -> None:
    raw = (
        b"id: cur_ping\n"
        b"event: ping\n"
        b'data: {"cursor":"cur_ping"}\n'
        b"\n"
        b"id: cur_event\n"
        b"event: event\n"
        b'data: {"id":"evt_1","status":"open","startAt":"2026-08-14T04:00:00Z"}\n'
        b"\n"
    )
    decoded = list(iter_sse(iter([raw])))
    assert decoded[0].event == "ping"
    assert decoded[0].id == "cur_ping"
    frames = [frame_from_sse(sse) for sse in decoded]
    assert frames[0] is None
    assert frames[1] is not None
    assert frames[1].type == "event"
    assert frames[1].cursor == "cur_event"


def test_error_frame_incomplete_snapshot_is_resync() -> None:
    raw = b'id: cur_err\nevent: error\ndata: {"code":"incomplete_snapshot","detail":"hydrate failed","traceId":"abc"}\n\n'
    events = list(SSEDecoder().iter_bytes(iter([raw])))
    with pytest.raises(ResyncRequired) as raised:
        frame_from_sse(events[0])
    assert raised.value.reason == "incomplete_snapshot"


def test_error_frame_other_codes_are_status_errors() -> None:
    from betwatch import APIStatusError

    raw = b'id: cur_err\nevent: error\ndata: {"code":"stream_unavailable","detail":"nats down","traceId":"abc"}\n\n'
    events = list(SSEDecoder().iter_bytes(iter([raw])))
    with pytest.raises(APIStatusError) as raised:
        frame_from_sse(events[0])
    assert raised.value.code == "stream_unavailable"
    assert raised.value.trace_id == "abc"


def test_frame_from_sse_raises_resync_and_stops_retry() -> None:
    raw = b'id: cur_rs\nevent: resync\ndata: {"reason":"canonical_merge"}\n\n'
    events = list(SSEDecoder().iter_bytes(iter([raw])))
    with pytest.raises(ResyncRequired) as raised:
        frame_from_sse(events[0])
    assert raised.value.cursor == "cur_rs"
    assert raised.value.reason == "canonical_merge"


def test_decoder_handles_crlf_and_multiline_data() -> None:
    raw = b'event: coverage\r\ndata: {"eventId":"evt_1","marketId":"mkt_1",\r\ndata: "sourceId":"sportsbet","state":"priced","complete":true}\r\n\r\n'
    events = list(SSEDecoder().iter_bytes(iter([raw])))
    assert len(events) == 1
    frame = frame_from_sse(events[0])
    assert frame is not None
    assert frame.type == "coverage"


def test_initial_cursor_becomes_last_event_id_and_snapshot_none() -> None:
    headers, query = stream_headers_and_query(
        {"snapshot": "full", "cursor": "old", "event": ["evt_1"]},
        "cur_from_snapshot",
    )
    assert headers["Last-Event-ID"] == "cur_from_snapshot"
    assert query["snapshot"] == "none"
    assert "cursor" not in query
    assert query["event"] == ["evt_1"]


def test_fresh_stream_keeps_snapshot_full_without_cursor() -> None:
    headers, query = stream_headers_and_query({"snapshot": "full", "event": ["evt_1"]}, None)
    assert "Last-Event-ID" not in headers
    assert query["snapshot"] == "full"


def test_default_event_window_is_around_now() -> None:
    from datetime import UTC, datetime, timedelta

    from betwatch._base_client import default_event_window

    start, end = default_event_window()
    now = datetime.now(UTC)
    start_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    assert start_at < now < end_at
    assert end_at - start_at <= timedelta(hours=28)


def test_stream_enter_retries_connect_error_when_reconnect() -> None:
    import httpx

    from betwatch import Betwatch
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none"}, reconnect=True)
    calls = {"n": 0}

    class FakeResponse:
        def iter_bytes(self):
            return iter(())

        def close(self) -> None:
            return None

    def fake_open() -> FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("refused")
        return FakeResponse()

    object.__setattr__(stream, "_open", fake_open)
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    import betwatch._client as client_mod

    original = client_mod.time.sleep
    object.__setattr__(client_mod.time, "sleep", fake_sleep)
    try:
        with stream:
            assert calls["n"] == 3
        assert slept and all(0 <= item <= 8 for item in slept)
    finally:
        object.__setattr__(client_mod.time, "sleep", original)
        client.close()


def test_stream_open_409_is_resync_required() -> None:
    from betwatch import Betwatch, ResyncRequired
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none"}, reconnect=True)

    class FakeResponse:
        status_code = 409
        headers = {"x-trace-id": "trace-409"}

        def read(self) -> bytes:
            return b'{"code":"cursor_scope_changed","detail":"cursor does not match this stream scope"}'

        def close(self) -> None:
            return None

    class FakeRaw:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        def send(self, request: object, stream: bool = False) -> FakeResponse:
            return FakeResponse()

        def close(self) -> None:
            return None

    object.__setattr__(client, "_raw", FakeRaw())
    try:
        with pytest.raises(ResyncRequired) as raised:
            stream._open()
        assert raised.value.reason == "cursor_scope_changed"
    finally:
        client.close()


def test_stream_enter_does_not_retry_auth_errors() -> None:
    from betwatch import AuthenticationError, Betwatch
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none"}, reconnect=True)
    calls = {"n": 0}

    def fake_open() -> object:
        calls["n"] += 1
        raise AuthenticationError("nope", status_code=401, path="/v1/stream")

    object.__setattr__(stream, "_open", fake_open)
    try:
        with pytest.raises(AuthenticationError):
            with stream:
                pass
        assert calls["n"] == 1
    finally:
        client.close()


def test_stream_clean_close_before_sync_is_resync() -> None:
    from betwatch import Betwatch, ResyncRequired
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "full"}, reconnect=True)

    class FakeResponse:
        def iter_bytes(self):
            return iter(
                (
                    b"id: cur_ready\nevent: ready\ndata: {\"cursor\":\"cur_ready\"}\n\n",
                    b"id: cur_ready\nevent: event\ndata: {\"id\":\"evt_1\",\"status\":\"open\"}\n\n",
                )
            )

        def close(self) -> None:
            return None

    object.__setattr__(stream, "_response", FakeResponse())
    try:
        with pytest.raises(ResyncRequired) as raised:
            list(stream)
        assert raised.value.reason == "incomplete_snapshot"
    finally:
        client.close()


def test_stream_keyboard_interrupt_closes_and_raises() -> None:
    from betwatch import Betwatch
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none"}, reconnect=False)
    closed = {"n": 0}

    class FakeResponse:
        def iter_bytes(self) -> object:
            raise KeyboardInterrupt

        def close(self) -> None:
            closed["n"] += 1

    object.__setattr__(stream, "_response", FakeResponse())
    with pytest.raises(KeyboardInterrupt):
        list(stream)
    assert closed["n"] >= 1
    client.close()
