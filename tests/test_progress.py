"""Bootstrap progress reporting.

The SDK owns this so every consumer gets it — an example that hand-rolls a
ticker is the thing this replaces.
"""

from __future__ import annotations

import time

import pytest

from betwatch import StreamProgress
from betwatch._progress import BootstrapReporter
from betwatch.types.stream import StreamFrame


def test_rendering_covers_the_three_bootstrap_states() -> None:
    waiting = StreamProgress(elapsed=15.0, frames=0, counts={})
    assert "waiting for the first frame" in str(waiting)
    assert "keepalive" not in str(waiting)

    alive = StreamProgress(elapsed=15.0, frames=0, counts={}, pings=2)
    assert "2 keepalives — connection is alive" in str(alive)

    one = StreamProgress(elapsed=15.0, frames=0, counts={}, pings=1)
    assert "1 keepalive —" in str(one), "singular, not '1 keepalives'"

    flowing = StreamProgress(elapsed=40.0, frames=5321, counts={"coverage": 663})
    assert "5321 frames" in str(flowing)
    assert "coverage=663" in str(flowing)

    done = StreamProgress(elapsed=95.0, frames=48044, counts={"event": 258}, synced=True)
    assert "bootstrap complete in 95s" in str(done)


def test_reporter_ticks_until_stopped_and_emits_a_final_report() -> None:
    seen: list[StreamProgress] = []
    reporter = BootstrapReporter(seen.append, interval=0.02)
    reporter.start()
    reporter.record("coverage")
    reporter.record("coverage")
    reporter.record_ping()
    deadline = time.monotonic() + 2.0
    while not seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen, "the ticker must report while the caller is blocked"
    reporter.stop(synced=True)

    final = seen[-1]
    assert final.synced
    assert final.frames == 2
    assert final.counts["coverage"] == 2
    assert final.pings == 1


def test_stop_is_idempotent_and_silent_without_sync() -> None:
    seen: list[StreamProgress] = []
    reporter = BootstrapReporter(seen.append, interval=30.0)
    reporter.start()
    reporter.stop()
    reporter.stop(synced=True)  # second call must not emit
    assert seen == []


def test_a_broken_reporter_never_kills_the_stream() -> None:
    def explode(_: StreamProgress) -> None:
        raise RuntimeError("callback is buggy")

    reporter = BootstrapReporter(explode, interval=0.02)
    reporter.start()
    time.sleep(0.1)
    reporter.stop(synced=True)  # must not raise


def test_progress_is_off_by_default_and_skipped_on_cursor_resume() -> None:
    from betwatch import Betwatch
    from betwatch._client import Stream

    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888")
    try:
        assert Stream(client, {"snapshot": "full"}, reconnect=False)._reporter is None
        assert (
            Stream(client, {"snapshot": "full"}, reconnect=False, progress=lambda _: None)._reporter
            is not None
        )
        # a cursor resume is live from the first frame; there is no bootstrap
        assert (
            Stream(client, {"snapshot": "none"}, reconnect=False, progress=lambda _: None)._reporter
            is None
        )
    finally:
        client.close()


@pytest.mark.parametrize("name", ["print_progress", "StreamProgress"])
def test_progress_api_is_public(name: str) -> None:
    import betwatch

    assert name in betwatch.__all__
    assert hasattr(betwatch, name)


# --- change tracking (the other thing examples used to hand-roll) ---------


def _odds(price: float, state: str = "available") -> StreamFrame:
    from betwatch.types.stream import frame_for_event

    return frame_for_event(
        "odds",
        "cur_1",
        {
            "id": "odd_1.a",
            "eventId": "evt_1",
            "marketId": "mkt_1.a",
            "outcomeId": "out_1.a",
            "source": {"id": "sportsbet", "name": "Sportsbet", "kind": "bookmaker"},
            "state": state,
            "price": price,
        },
    )


def test_first_sight_is_a_change_and_a_republish_is_not() -> None:
    from betwatch import ChangeTracker

    tracker = ChangeTracker()
    assert tracker.changed(_odds(3.2)) is True
    assert tracker.changed(_odds(3.2)) is False, "same price republished"
    assert tracker.changed(_odds(3.4)) is True, "price moved"
    assert tracker.changed(_odds(3.4, state="suspended")) is True, "state moved"


def test_sources_are_tracked_separately() -> None:
    from betwatch import ChangeTracker
    from betwatch.types.stream import frame_for_event

    tracker = ChangeTracker()

    def row(source: str) -> StreamFrame:
        return frame_for_event(
            "odds",
            "cur_1",
            {
                "id": f"odd_1.{source}",
                "eventId": "evt_1",
                "marketId": "mkt_1.a",
                "outcomeId": "out_1.a",
                "source": {"id": source, "name": source, "kind": "bookmaker"},
                "state": "available",
                "price": 3.2,
            },
        )

    assert tracker.changed(row("sportsbet")) is True
    assert tracker.changed(row("tab")) is True, "same price, different source, still news"


def test_clear_forgets_everything_for_a_resync() -> None:
    from betwatch import ChangeTracker

    tracker = ChangeTracker()
    tracker.changed(_odds(3.2))
    assert len(tracker) == 1
    tracker.clear()
    assert len(tracker) == 0
    assert tracker.changed(_odds(3.2)) is True, "after a resync, state is news again"


def test_unknown_frame_kinds_are_always_a_change() -> None:
    """Never silently swallow something the SDK does not model yet."""
    from betwatch import ChangeTracker
    from betwatch.types.stream import frame_for_event

    tracker = ChangeTracker()
    weather = frame_for_event("weather", "cur_1", {"rain": True})
    assert tracker.changed(weather) is True
    assert tracker.changed(weather) is True


def test_odds_rows_can_be_filtered_individually() -> None:
    """odds_set carries many rows; a caller unpacking it filters per row."""
    from betwatch import ChangeTracker
    from betwatch.types.stream import frame_for_event, iter_odds

    def price_set(prices: list[float]) -> StreamFrame:
        return frame_for_event(
            "odds_set",
            "cur_1",
            {
                "eventId": "evt_1",
                "marketId": "mkt_1.a",
                "items": [
                    {
                        "id": f"odd_1.{i}",
                        "eventId": "evt_1",
                        "marketId": "mkt_1.a",
                        "outcomeId": f"out_1.{i}",
                        "source": {"id": "sportsbet", "name": "Sportsbet", "kind": "bookmaker"},
                        "state": "available",
                        "price": p,
                    }
                    for i, p in enumerate(prices)
                ],
            },
        )

    tracker = ChangeTracker()
    assert [tracker.changed(q) for q in iter_odds(price_set([3.2, 4.0]))] == [True, True]
    assert [tracker.changed(q) for q in iter_odds(price_set([3.2, 4.5]))] == [False, True]


def test_a_lost_bootstrap_is_reported_not_silent() -> None:
    """A dropped connection before sync discards everything; say so.

    Silently restarting is indistinguishable from a slow bootstrap, which is
    how a stream that can never finish looks like one that is merely taking
    its time.
    """
    from betwatch._progress import BootstrapReporter

    seen: list[StreamProgress] = []
    reporter = BootstrapReporter(seen.append, interval=30.0)
    reporter.start()
    reporter.record("coverage")
    reporter.record("coverage")
    reporter.record_restart()

    assert seen, "the restart itself must produce a report"
    assert seen[-1].restarts == 1
    assert seen[-1].frames == 0, "counts reset — those frames are gone"
    assert "restarted 1x" in str(seen[-1])
    reporter.stop()


def test_read_timeout_outlasts_the_silent_bootstrap_window() -> None:
    """Measured silences reached 46s; a 45s timeout aborted healthy streams."""
    from betwatch._base_client import STREAM_READ_TIMEOUT

    assert STREAM_READ_TIMEOUT > 60, "must survive a snapshot that sends nothing for ~46s"


# --- resync budget --------------------------------------------------------


def test_resync_budget_is_consecutive_not_lifetime() -> None:
    """A worker restart broadcasts resync to every client, so they are routine.

    A lifetime cap would kill a week-long consumer on its eighth ordinary
    resync. The budget is for consecutive failures to re-bootstrap.
    """
    import inspect

    from betwatch import _client

    source = inspect.getsource(_client)
    assert "_resyncs > 8" not in source, "lifetime cap"
    assert source.count("self._resyncs = 0") >= 3, "reset once frames flow, in each watcher"
    assert _client.MAX_CONSECUTIVE_RESYNCS >= 3


def test_bootstrap_restarts_are_bounded() -> None:
    """An unbounded restart loop is a hang, not resilience."""
    from betwatch import BootstrapFailedError
    from betwatch._client import MAX_BOOTSTRAP_RESTARTS

    assert MAX_BOOTSTRAP_RESTARTS >= 1
    err = BootstrapFailedError(4, ["thoroughbred"])
    assert "restarted 4 times" in str(err)
    assert "client.snapshot(" in str(err), "must name the way out"
