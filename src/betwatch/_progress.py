"""Bootstrap progress for `snapshot=full` streams.

A broad `snapshot=full` sends nothing at all for tens of seconds while the
server builds the snapshot, then delivers thousands of frames. Keepalives are
swallowed by the frame policy, so a caller iterating the stream has nothing to
observe and no way to tell "still building" from "connection died".

`Stream(progress=...)` runs a timer alongside the iteration and reports
elapsed time and frame counts until the `sync` frame arrives. Every consumer
wants this, so it lives here rather than in each caller.
"""

from __future__ import annotations

import asyncio
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic

DEFAULT_INTERVAL = 5.0


@dataclass(frozen=True, slots=True)
class StreamProgress:
    """One bootstrap progress report."""

    elapsed: float
    """Seconds since the stream was opened."""

    frames: int
    """Frames delivered so far, across every kind."""

    counts: Mapping[str, int]
    """Frames so far by name: `event`, `entrant`, `odds_set`, `coverage`, …"""

    pings: int = 0
    """Keepalives seen. Non-zero during a silent bootstrap means the connection
    is alive and the server is still building — not that it has hung."""

    restarts: int = 0
    """Times the bootstrap started over after losing the connection.

    A dropped connection before `sync` discards every frame received so far —
    there is no resumable position until the snapshot completes — so the counts
    above reset with it. A number climbing here means the snapshot is taking
    longer to build than the connection is surviving."""

    synced: bool = False
    """True on the final report, once `sync` has arrived and live ticks begin."""

    def __str__(self) -> str:
        restarted = f" (restarted {self.restarts}x)" if self.restarts else ""
        if self.synced:
            detail = " ".join(f"{name}={n}" for name, n in sorted(self.counts.items()) if n)
            return f"bootstrap complete in {self.elapsed:.0f}s{restarted} — {self.frames} frames {detail}"
        if not self.frames:
            plural = "" if self.pings == 1 else "s"
            alive = f", {self.pings} keepalive{plural} — connection is alive" if self.pings else ""
            return (
                f"bootstrap +{self.elapsed:.0f}s{restarted} waiting for the first frame"
                f"{alive} (the server is building the snapshot; narrower filters are faster)"
            )
        detail = " ".join(f"{name}={n}" for name, n in sorted(self.counts.items()) if n)
        return f"bootstrap +{self.elapsed:.0f}s{restarted} {self.frames} frames {detail}"


ProgressCallback = Callable[[StreamProgress], None]


def print_progress(progress: StreamProgress) -> None:
    """Ready-made reporter: `client.stream(..., progress=print_progress)`."""
    print(progress, flush=True)


@dataclass
class _State:
    started: float = field(default_factory=monotonic)
    counts: Counter[str] = field(default_factory=Counter)
    pings: int = 0
    restarts: int = 0

    def record(self, name: str) -> None:
        self.counts[name] += 1

    def snapshot(self, *, synced: bool = False) -> StreamProgress:
        return StreamProgress(
            elapsed=monotonic() - self.started,
            frames=sum(self.counts.values()),
            counts=dict(self.counts),
            pings=self.pings,
            restarts=self.restarts,
            synced=synced,
        )


class BootstrapReporter:
    """Calls `callback` every `interval` seconds until stopped.

    Reports from a daemon thread so a blocked iterator still produces output.
    `record()` is called from the iterating thread; `Counter` increments under
    the GIL are safe enough here, and a report one frame stale is harmless.
    """

    def __init__(self, callback: ProgressCallback, *, interval: float = DEFAULT_INTERVAL) -> None:
        self._callback = callback
        self._interval = interval
        self._state = _State()
        self._done = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def record(self, name: str) -> None:
        self._state.record(name)

    def record_ping(self) -> None:
        self._state.pings += 1

    def record_restart(self) -> None:
        """The connection dropped before `sync`; everything counted is gone."""
        self._state.restarts += 1
        self._state.counts.clear()
        self._emit(self._state.snapshot())

    def stop(self, *, synced: bool = False) -> None:
        """Idempotent. On `synced`, emits one final report."""
        if self._done.is_set():
            return
        self._done.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=1.0)
        if synced:
            self._emit(self._state.snapshot(synced=True))

    def _run(self) -> None:
        while not self._done.wait(self._interval):
            self._emit(self._state.snapshot())

    def _emit(self, progress: StreamProgress) -> None:
        try:
            self._callback(progress)
        except Exception:  # noqa: BLE001 - a reporter must never kill the stream
            pass


class AsyncBootstrapReporter(BootstrapReporter):
    """Same contract on an asyncio task, so nothing blocks the loop."""

    def __init__(self, callback: ProgressCallback, *, interval: float = DEFAULT_INTERVAL) -> None:
        super().__init__(callback, interval=interval)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._arun())

    def stop(self, *, synced: bool = False) -> None:
        if self._done.is_set():
            return
        self._done.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
        if synced:
            self._emit(self._state.snapshot(synced=True))

    async def _arun(self) -> None:
        try:
            while not self._done.is_set():
                await asyncio.sleep(self._interval)
                if self._done.is_set():
                    return
                self._emit(self._state.snapshot())
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            return
