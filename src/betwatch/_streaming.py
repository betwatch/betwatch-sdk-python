# SSE field semantics follow https://html.spec.whatwg.org/multipage/server-sent-events.html,
# originally adapted from https://github.com/florimondmanca/httpx-sse.
from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

import msgspec

from ._compat import decode_json
from ._exceptions import APIStatusError, ResyncRequired, StreamDecodeError
from .types.stream import StreamCursor, StreamError, StreamFrame, StreamResync, frame_for_event


class ServerSentEvent:
    """One dispatched SSE event. `data` stays bytes until something asks for text."""

    __slots__ = ("event", "id", "raw", "retry")

    def __init__(
        self,
        *,
        event: str | None = None,
        data: bytes | str | None = None,
        id: str | None = None,
        retry: int | None = None,
    ) -> None:
        self.event = event or None
        self.raw = data.encode() if isinstance(data, str) else (data or b"")
        self.id = id
        self.retry = retry

    @property
    def data(self) -> str:
        return self.raw.decode("utf-8", "replace")

    def json(self) -> Any:
        return msgspec.json.decode(self.raw) if self.raw else None

    def __repr__(self) -> str:
        return (
            f"ServerSentEvent(event={self.event}, data={self.data}, "
            f"id={self.id}, retry={self.retry})"
        )


def _lines(chunks: Iterable[bytes], state: list[bytes]) -> Iterator[bytes]:
    """Split one batch of chunks into complete lines; carry the partial tail in `state`.

    Splits once per chunk rather than once per line, and keeps a long partial
    line as a list of parts so a 200 KB `odds_set` arriving in small reads is
    joined once instead of copied on every read.
    """
    for chunk in chunks:
        if b"\r" in chunk or (state and state[-1].endswith(b"\r")):
            if state:
                chunk = b"".join(state) + chunk
                state.clear()
            # A trailing CR may be the first half of a CRLF split across reads.
            held = chunk.endswith(b"\r")
            if held:
                chunk = chunk[:-1]
            chunk = chunk.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            if held:
                chunk += b"\r"
        parts = chunk.split(b"\n")
        tail = parts.pop()
        if parts:
            if state:
                state.append(parts[0])
                parts[0] = b"".join(state)
                state.clear()
            yield from parts
        if tail:
            state.append(tail)


class SSEDecoder:
    def __init__(self) -> None:
        self._event: str | None = None
        self._data: list[bytes] = []
        self._last_event_id: str | None = None
        self._retry: int | None = None
        self._partial: list[bytes] = []

    def _feed(self, chunks: Iterable[bytes]) -> Iterator[ServerSentEvent]:
        for line in _lines(chunks, self._partial):
            if (sse := self._line(line)) is not None:
                yield sse

    def _finish(self) -> ServerSentEvent | None:
        """End of stream. A held-back CR was a terminator after all, so its line
        is complete; an event never closed by a blank line is not dispatched."""
        if not self._partial:
            return None
        tail = b"".join(self._partial)
        self._partial.clear()
        return self._line(tail[:-1] if tail.endswith(b"\r") else tail)

    def iter_bytes(self, iterator: Iterable[bytes]) -> Iterator[ServerSentEvent]:
        for chunk in iterator:
            yield from self._feed((chunk,))
        if (sse := self._finish()) is not None:
            yield sse

    async def aiter_bytes(self, iterator: AsyncIterator[bytes]) -> AsyncIterator[ServerSentEvent]:
        async for chunk in iterator:
            for sse in self._feed((chunk,)):
                yield sse
        if (sse := self._finish()) is not None:
            yield sse

    def decode(self, line: str) -> ServerSentEvent | None:
        """Feed one line of text (no terminator). Returns an event on a blank line."""
        return self._line(line.encode())

    def _line(self, line: bytes) -> ServerSentEvent | None:
        if not line:
            if (
                not self._event
                and not self._data
                and not self._last_event_id
                and self._retry is None
            ):
                return None
            data = self._data
            sse = ServerSentEvent(
                event=self._event,
                data=data[0] if len(data) == 1 else b"\n".join(data),
                id=self._last_event_id,
                retry=self._retry,
            )
            self._event = None
            self._data = []
            self._retry = None
            return sse

        if line[:1] == b":":
            return None

        fieldname, _, value = line.partition(b":")
        if value[:1] == b" ":
            value = value[1:]

        if fieldname == b"data":
            self._data.append(value)
        elif fieldname == b"event":
            self._event = value.decode("utf-8", "replace")
        elif fieldname == b"id":
            if b"\0" not in value:
                self._last_event_id = value.decode("utf-8", "replace")
        elif fieldname == b"retry":
            try:
                self._retry = int(value)
            except ValueError:
                pass
        return None


# Control frames carry the position itself, so they cannot be id-less.
_CURSOR_FRAMES = frozenset({"ready", "sync", "ping"})


def _control(sse: ServerSentEvent, model: type[Any]) -> Any:
    try:
        return decode_json(sse.raw or b"{}", model)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        raise StreamDecodeError(sse.event or "", sse.id, exc) from exc


def frame_from_sse(sse: ServerSentEvent) -> StreamFrame | None:
    """Apply Betwatch stream policy to one decoded SSE event.

    `ping` is consumed (cursor still advances via sse.id) and never yielded.
    `resync` stops automatic retry. Snapshot frames of a `snapshot=full`
    bootstrap arrive before any id, so their `cursor` is None; `sync` carries
    the first resumable one.
    """
    event = sse.event
    if event is None:
        return None
    if sse.id == "" or (event in _CURSOR_FRAMES and not sse.id):
        # An explicit empty id resets the SSE last-event-id. Accepting it would
        # silently resume from a stale position, so fail closed.
        raise StreamDecodeError(event, sse.id, "frame requires a non-empty SSE id")
    if event in _CURSOR_FRAMES:
        control = _control(sse, StreamCursor)
        if control.cursor != sse.id:
            raise StreamDecodeError(event, sse.id, "payload cursor does not match SSE id")
        if event == "ping":
            return None
    elif event == "resync":
        parsed = _control(sse, StreamResync)
        raise ResyncRequired(sse.id, parsed.reason, parsed.resync_token)
    elif event == "error":
        stream_error = _control(sse, StreamError)
        if stream_error.code == "incomplete_snapshot":
            raise ResyncRequired(sse.id, stream_error.code)
        raise APIStatusError(
            f"/v2/stream failed: {stream_error.detail}",
            status_code=503,
            body=sse.json(),
            path="/v2/stream",
            trace_id=stream_error.trace_id,
        )
    try:
        return frame_for_event(event, sse.id, sse.raw)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        raise StreamDecodeError(event, sse.id, exc) from exc


def iter_sse(chunks: Iterable[bytes]) -> Iterator[ServerSentEvent]:
    yield from SSEDecoder().iter_bytes(chunks)


async def aiter_sse(chunks: AsyncIterator[bytes]) -> AsyncIterator[ServerSentEvent]:
    async for sse in SSEDecoder().aiter_bytes(chunks):
        yield sse
