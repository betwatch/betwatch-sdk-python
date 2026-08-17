from __future__ import annotations

import pytest

from betwatch import OddsFrame, ResyncRequired, StreamDecodeError
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


def test_ping_payload_cursor_must_match_sse_id() -> None:
    raw = b'id: cur_1\nevent: ping\ndata: {"cursor":"cur_2"}\n\n'
    event = list(SSEDecoder().iter_bytes(iter([raw])))[0]
    with pytest.raises(StreamDecodeError, match="does not match"):
        frame_from_sse(event)


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


def test_malformed_known_frame_is_not_downgraded_to_unknown() -> None:
    raw = b'id: cur_bad\nevent: odds\ndata: {"id":"odd_1"}\n\n'
    event = list(SSEDecoder().iter_bytes(iter([raw])))[0]
    with pytest.raises(StreamDecodeError) as raised:
        frame_from_sse(event)
    assert raised.value.event == "odds"
    assert raised.value.cursor == "cur_bad"


def test_valid_future_frame_remains_forward_compatible() -> None:
    from betwatch import UnknownFrame

    raw = b'id: cur_future\nevent: dividend\ndata: {"amountCents":123}\n\n'
    event = list(SSEDecoder().iter_bytes(iter([raw])))[0]
    frame = frame_from_sse(event)
    assert isinstance(frame, UnknownFrame)
    assert frame.name == "dividend"


def test_empty_event_id_fails_closed_instead_of_reusing_stale_cursor() -> None:
    raw = b'id:\nevent: ping\ndata: {"cursor":""}\n\n'
    event = list(SSEDecoder().iter_bytes(iter([raw])))[0]
    assert event.id == ""
    with pytest.raises(StreamDecodeError):
        frame_from_sse(event)


def test_decoder_handles_crlf_and_multiline_data() -> None:
    raw = b'id: cur_coverage\r\nevent: coverage\r\ndata: {"eventId":"evt_1","marketId":"mkt_1",\r\ndata: "sourceId":"sportsbet","state":"priced","complete":true}\r\n\r\n'
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


def test_stream_enter_does_not_retry_server_status() -> None:
    from betwatch import Betwatch, InternalServerError
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none"}, reconnect=True)
    calls = {"n": 0}

    def fake_open() -> object:
        calls["n"] += 1
        raise InternalServerError("down", status_code=503, path="/v1/stream")

    object.__setattr__(stream, "_open", fake_open)
    try:
        with pytest.raises(InternalServerError):
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
                    b'id: cur_ready\nevent: ready\ndata: {"cursor":"cur_ready"}\n\n',
                    b'id: cur_ready\nevent: event\ndata: {"id":"evt_1","status":"open"}\n\n',
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


def test_resume_reconnects_with_the_last_frame_id_not_the_original_cursor() -> None:
    """A drop mid-stream resumes at the last frame applied, not where we started."""
    import httpx

    from betwatch import Betwatch, OddsFrame
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://127.0.0.1:9")
    stream = Stream(client, {"snapshot": "none", "cursor": "cur_start"}, reconnect=True)

    row = (
        b'{"id":"odd_1.a","eventId":"evt_1","marketId":"mkt_1.a","outcomeId":"out_1.a",'
        b'"source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},'
        b'"state":"available","price":3.4}'
    )
    first = b'event: sync\nid: cur_sync\ndata: {"cursor":"cur_sync"}\n\n'
    first += b"event: odds\nid: cur_last\ndata: " + row + b"\n\n"

    opens: list[str | None] = []

    class FakeResponse:
        def __init__(self, chunks: bytes) -> None:
            self._chunks = chunks

        def iter_bytes(self):
            yield self._chunks
            raise httpx.ReadError("dropped")

        def close(self) -> None:
            return None

    def fake_open() -> FakeResponse:
        opens.append(stream.cursor)
        if len(opens) == 1:
            return FakeResponse(first)
        raise KeyboardInterrupt  # stop the test once we have seen the resume cursor

    object.__setattr__(stream, "_open", fake_open)
    try:
        with pytest.raises(KeyboardInterrupt):
            for frame in stream:
                assert isinstance(frame, (OddsFrame, type(frame)))
    finally:
        client.close()

    assert opens[0] == "cur_start", "first connect uses the bootstrap cursor"
    assert opens[1] == "cur_last", "the resume uses the last frame id, not cur_start"


def _snapshot_bytes(cursor: str) -> bytes:
    return (
        b'{"stream":{"cursor":"' + cursor.encode() + b'","event":["evt_1"],'
        b'"source":["sportsbet"]},"event":{"id":"evt_1","sport":"thoroughbred",'
        b'"name":"R1","startAt":"2026-08-15T04:00:00Z","status":"open"},'
        b'"entrants":[],"markets":[],"outcomes":[],"odds":[],"coverage":[]}'
    )


def test_409_cursor_expired_recovers_by_re_bootstrapping_over_rest() -> None:
    """The documented recovery, end to end.

    A dead cursor raises ResyncRequired rather than reconnecting with it; the
    caller re-snapshots over REST and follows the fresh cursor, which is what
    goes out as Last-Event-ID.
    """
    import httpx

    from betwatch import Betwatch, CursorError, ResyncRequired
    from betwatch._base_client import decode_model
    from betwatch.types.snapshot import EventSnapshot

    stale = decode_model("/v1/events/evt_1/snapshot", _snapshot_bytes("cur_stale"), EventSnapshot)
    fresh = decode_model("/v1/events/evt_1/snapshot", _snapshot_bytes("cur_fresh"), EventSnapshot)

    sent: list[dict[str, str]] = []

    class Raw:
        def __init__(self) -> None:
            self.opens = 0

        def build_request(self, method, url, *, params, headers, timeout):
            return httpx.Request(
                method, "http://localhost:8888" + url, params=params, headers=headers
            )

        def send(self, request, *, stream):
            self.opens += 1
            sent.append(dict(request.headers))
            if self.opens == 1:
                return httpx.Response(
                    409,
                    request=request,
                    json={
                        "type": "x",
                        "title": "Conflict",
                        "status": 409,
                        "detail": "cursor is older than your replay window",
                        "code": "cursor_expired",
                        "requestId": "01K3F9QW2H",
                    },
                )
            return httpx.Response(200, request=request, content=b"")

        def close(self) -> None:
            return None

    raw = Raw()
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888")
    object.__setattr__(client, "_raw", raw)
    try:
        with pytest.raises(ResyncRequired) as caught:
            with client.follow(stale, reconnect=False):
                pass

        assert caught.value.reason == "cursor_expired"
        assert caught.value.cursor == "cur_stale"
        cause = caught.value.__cause__
        assert isinstance(cause, CursorError), type(cause)
        assert cause.status_code == 409
        assert cause.request_id == "01K3F9QW2H"

        # the documented recovery: bootstrap again, follow the cursor it returned
        with client.follow(fresh, reconnect=False):
            pass
    finally:
        client.close()

    assert raw.opens == 2
    assert sent[0]["last-event-id"] == "cur_stale"
    assert sent[1]["last-event-id"] == "cur_fresh", "must reconnect with the fresh cursor"
    assert all("bw_test" not in str(h.get("last-event-id", "")) for h in sent)


def test_a_dead_cursor_is_never_retried_with_itself() -> None:
    """Reconnecting with an expired cursor is an infinite loop, so it must not happen."""
    import httpx

    from betwatch import Betwatch, ResyncRequired

    class Raw:
        def __init__(self) -> None:
            self.opens = 0

        def build_request(self, method, url, *, params, headers, timeout):
            return httpx.Request(
                method, "http://localhost:8888" + url, params=params, headers=headers
            )

        def send(self, request, *, stream):
            self.opens += 1
            return httpx.Response(
                409,
                request=request,
                json={
                    "type": "x",
                    "title": "Conflict",
                    "status": 409,
                    "detail": "cursor was minted for a different filter set",
                    "code": "cursor_scope_changed",
                    "requestId": "01K3F9QW2H",
                },
            )

        def close(self) -> None:
            return None

    raw = Raw()
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888")
    object.__setattr__(client, "_raw", raw)
    stream = client.stream(event="evt_1", cursor="cur_wrong_scope", reconnect=True)
    try:
        with pytest.raises(ResyncRequired):
            with stream:
                pass
    finally:
        client.close()

    assert raw.opens == 1, "reconnect=True must not retry a cursor the server rejected"
