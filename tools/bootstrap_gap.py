#!/usr/bin/env python
"""Does a `snapshot=full` stream miss changes published while it is building?

`ready` is flushed within a second, then the server spends 20-45s hydrating the
snapshot. Anything that changes during that window is either replayed to us
afterwards or silently lost, and the difference matters: a lost change means we
hold a stale price until that source moves again.

The test, for one scope:

  1. Stream `snapshot=full`, recording every odds row and the wall-clock
     instants of `ready` and `sync`.
  2. The moment `sync` lands, read the same scope over REST. That is the
     authoritative current state.
  3. Compare. A row where REST disagrees with what we streamed, *and* whose
     REST `updatedAt` falls inside the bootstrap window, is a change published
     during generation that never reached us.
  4. Separately, watch the frames arriving just after `sync`. If the server
     replays the window, some of them carry an `updatedAt` from inside it.

Rows whose REST `updatedAt` is after `sync` are ordinary live movement and are
excluded — they are not evidence of anything.

    fnox exec --profile prod -- uv run tools/bootstrap_gap.py --sport thoroughbred --country au
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from time import monotonic

from betwatch import (
    APIConnectionError,
    Betwatch,
    Odds,
    ReadyFrame,
    ResyncRequired,
    SyncFrame,
)
from betwatch.types.stream import iter_odds

Key = tuple[str, str, str]


def _key(row: Odds) -> Key:
    return (row.market_id, row.outcome_id, row.source.id)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sport", action="append", choices=["thoroughbred", "greyhound", "harness"])
    p.add_argument("--country", action="append")
    p.add_argument("--watch-after-sync", type=float, default=20.0)
    p.add_argument("--timeout", type=float, default=240.0)
    p.add_argument("--events", type=int, default=50, help="How many events to verify over REST.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scope = {"sport": args.sport or ["thoroughbred"], "country": args.country or ["au"]}

    streamed: dict[Key, Odds] = {}
    replayed_from_window: list[tuple[Key, datetime]] = []
    t_ready = t_sync = None
    synced_at = 0.0
    started = monotonic()

    dropped = False
    with Betwatch() as client:
        print(f"host={client.base_url} scope={scope}", flush=True)
        try:
            with client.stream(**scope, snapshot="full", reconnect=False) as stream:
                for frame in stream:
                    now = monotonic()
                    if isinstance(frame, ReadyFrame):
                        t_ready = datetime.now(UTC)
                        print(f"ready at {t_ready.isoformat()}", flush=True)
                        continue
                    if isinstance(frame, SyncFrame):
                        t_sync = datetime.now(UTC)
                        synced_at = now
                        print(
                            f"sync at {t_sync.isoformat()} "
                            f"({(t_sync - t_ready).total_seconds():.1f}s window, "
                            f"{len(streamed)} odds rows) — watching "
                            f"{args.watch_after_sync:.0f}s for replayed changes",
                            flush=True,
                        )
                        continue
                    for row in iter_odds(frame):
                        if t_sync is None:
                            streamed[_key(row)] = row
                        elif row.updated_at and t_ready <= row.updated_at <= t_sync:
                            # published while the snapshot was building, delivered after
                            replayed_from_window.append((_key(row), row.updated_at))
                    if t_sync is not None and now - synced_at > args.watch_after_sync:
                        break
                    if now - started > args.timeout:
                        print("TIMED OUT before sync", flush=True)
                        return 1

        except (APIConnectionError, ResyncRequired) as exc:
            dropped = True
            print(f"STREAM ENDED EARLY: {type(exc).__name__}: {exc}", flush=True)

        if t_ready is None or t_sync is None:
            print("never reached sync — the connection did not survive the bootstrap", flush=True)
            return 1

        # 2. authoritative current state. /v1/odds needs an event-shaped filter,
        #    so read back the events the snapshot itself gave us (50 max per call).
        event_ids = sorted({row.event_id for row in streamed.values()})[: args.events]
        rest: dict[Key, Odds] = {}
        for start in range(0, len(event_ids), 50):
            for row in client.odds.iter(event=event_ids[start : start + 50]):
                rest[_key(row)] = row
        t_rest = datetime.now(UTC)
        print(
            f"rest read {len(rest)} rows across {len(event_ids)} events by {t_rest.isoformat()}",
            flush=True,
        )

        # 3. disagreements whose change landed inside the bootstrap window
        missed: list[tuple[Key, float | None, float | None, datetime]] = []
        stale_after_sync = 0
        for key, rest_row in rest.items():
            streamed_row = streamed.get(key)
            if streamed_row is None or rest_row.price == streamed_row.price:
                continue
            changed_at = rest_row.updated_at
            if changed_at is None:
                continue
            if t_ready <= changed_at <= t_sync:
                missed.append((key, streamed_row.price, rest_row.price, changed_at))
            elif changed_at > t_sync:
                stale_after_sync += 1

    window = (t_sync - t_ready).total_seconds()
    print("\n" + "=" * 72)
    print(
        f"bootstrap window          {window:.1f}s  ({t_ready.isoformat()} -> {t_sync.isoformat()})"
    )
    print(f"odds rows streamed        {len(streamed)}")
    print(f"odds rows over REST       {len(rest)}")
    print(f"rows changed after sync   {stale_after_sync}  (ordinary live movement, not evidence)")
    print(
        f"REPLAYED FROM WINDOW      {len(replayed_from_window)}  (post-sync frames dated inside the window)"
    )
    print(f"connection dropped        {dropped}")
    print(f"MISSED CHANGES            {len(missed)}")
    for key, streamed_price, rest_price, changed_at in missed[:20]:
        print(
            f"  {key}  streamed={streamed_price} rest={rest_price} changed_at={changed_at.isoformat()}"
        )
    if len(missed) > 20:
        print(f"  … and {len(missed) - 20} more")

    if missed:
        print("\nVERDICT: changes published during snapshot generation did NOT reach the client.")
        return 2
    print("\nVERDICT: no missed changes detected in this window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
