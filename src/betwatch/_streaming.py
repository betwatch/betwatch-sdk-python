# Decoder initially copied from https://github.com/florimondmanca/httpx-sse
# and the Stainless Python runtime used by openai-python / anthropic-sdk-python.
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import msgspec

from ._exceptions import APIStatusError, ResyncRequired, StreamDecodeError
from .types.stream import StreamCursor, StreamError, StreamFrame, StreamResync, frame_for_event


class ServerSentEvent:
    def __init__(
        self,
        *,
        event: str | None = None,
        data: str | None = None,
        id: str | None = None,
        retry: int | None = None,
    ) -> None:
        self._id = id
        self._data = data or ""
        self._event = event or None
        self._retry = retry

    @property
    def event(self) -> str | None:
        return self._event

    @property
    def id(self) -> str | None:
        return self._id

    @property
    def retry(self) -> int | None:
        return self._retry

    @property
    def data(self) -> str:
        return self._data

    def json(self) -> Any:
        if not self.data:
            return None
        return json.loads(self.data)

    def __repr__(self) -> str:
        return (
            f"ServerSentEvent(event={self.event}, data={self.data}, "
            f"id={self.id}, retry={self.retry})"
        )


class SSEDecoder:
    def __init__(self) -> None:
        self._event: str | None = None
        self._data: list[str] = []
        self._last_event_id: str | None = None
        self._retry: int | None = None

    def iter_bytes(self, iterator: Iterator[bytes]) -> Iterator[ServerSentEvent]:
        for chunk in self._iter_chunks(iterator):
            for raw_line in chunk.splitlines():
                sse = self.decode(raw_line.decode("utf-8"))
                if sse:
                    yield sse

    def _iter_chunks(self, iterator: Iterator[bytes]) -> Iterator[bytes]:
        data = b""
        for chunk in iterator:
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    async def aiter_bytes(self, iterator: AsyncIterator[bytes]) -> AsyncIterator[ServerSentEvent]:
        async for chunk in self._aiter_chunks(iterator):
            for raw_line in chunk.splitlines():
                sse = self.decode(raw_line.decode("utf-8"))
                if sse:
                    yield sse

    async def _aiter_chunks(self, iterator: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        data = b""
        async for chunk in iterator:
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    def decode(self, line: str) -> ServerSentEvent | None:
        if not line:
            if (
                not self._event
                and not self._data
                and not self._last_event_id
                and self._retry is None
            ):
                return None
            sse = ServerSentEvent(
                event=self._event,
                data="\n".join(self._data),
                id=self._last_event_id,
                retry=self._retry,
            )
            self._event = None
            self._data = []
            self._retry = None
            return sse

        if line.startswith(":"):
            return None

        fieldname, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]

        if fieldname == "event":
            self._event = value
        elif fieldname == "data":
            self._data.append(value)
        elif fieldname == "id":
            if "\0" not in value:
                self._last_event_id = value
        elif fieldname == "retry":
            try:
                self._retry = int(value)
            except (TypeError, ValueError):
                pass
        return None


def frame_from_sse(sse: ServerSentEvent) -> StreamFrame | None:
    """Apply Betwatch stream policy to one decoded SSE event.

    `ping` is consumed (cursor still advances via sse.id) and never yielded.
    `resync` stops automatic retry.
    """
    if sse.event is None:
        return None
    if not sse.id:
        raise StreamDecodeError(sse.event, sse.id, "named frames require a non-empty SSE id")
    try:
        payload = sse.json()
    except (TypeError, ValueError) as exc:
        raise StreamDecodeError(sse.event, sse.id, exc) from exc
    if sse.event == "ping":
        try:
            ping = msgspec.convert(payload, type=StreamCursor)
        except (TypeError, msgspec.ValidationError) as exc:
            raise StreamDecodeError(sse.event, sse.id, exc) from exc
        if ping.cursor != sse.id:
            raise StreamDecodeError(sse.event, sse.id, "payload cursor does not match SSE id")
        return None
    if sse.event in {"ready", "sync"}:
        try:
            control = msgspec.convert(payload, type=StreamCursor)
        except (TypeError, msgspec.ValidationError) as exc:
            raise StreamDecodeError(sse.event, sse.id, exc) from exc
        if control.cursor != sse.id:
            raise StreamDecodeError(sse.event, sse.id, "payload cursor does not match SSE id")
    if sse.event == "resync":
        try:
            parsed = msgspec.convert(payload, type=StreamResync)
        except (TypeError, msgspec.ValidationError) as exc:
            raise StreamDecodeError(sse.event, sse.id, exc) from exc
        raise ResyncRequired(sse.id, parsed.reason)
    if sse.event == "error":
        try:
            stream_error = msgspec.convert(payload, type=StreamError)
        except (TypeError, msgspec.ValidationError) as exc:
            raise StreamDecodeError(sse.event, sse.id, exc) from exc
        if stream_error.code == "incomplete_snapshot":
            raise ResyncRequired(sse.id, stream_error.code)
        raise APIStatusError(
            f"/v1/stream failed: {stream_error.detail}",
            status_code=503,
            body=payload,
            path="/v1/stream",
            trace_id=stream_error.trace_id,
        )
    try:
        return frame_for_event(sse.event, sse.id, payload)
    except (TypeError, msgspec.DecodeError, msgspec.ValidationError) as exc:
        raise StreamDecodeError(sse.event, sse.id, exc) from exc


def iter_sse(chunks: Iterator[bytes]) -> Iterator[ServerSentEvent]:
    yield from SSEDecoder().iter_bytes(chunks)


async def aiter_sse(chunks: AsyncIterator[bytes]) -> AsyncIterator[ServerSentEvent]:
    async for sse in SSEDecoder().aiter_bytes(chunks):
        yield sse
