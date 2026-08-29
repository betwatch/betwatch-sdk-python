#!/usr/bin/env python
"""Does anything change between reading a snapshot and following its cursor?

`GET /v2/events/snapshot` anchors its cursor before it reads, so every change published
while the read was in flight should replay once you connect. If that were wrong
a client would silently hold a stale price until that source moved again — the
worst failure available here, because nothing announces it.

The test, for one scope:

  1. `client.snapshot(...)`, recording every price and the wall-clock window the
     read occupied.
  2. `client.follow(snap)` and watch, looking for frames whose `updatedAt` falls
     inside that window. Those are the replay, and seeing them is the guarantee
     working rather than merely not failing.
  3. Read the same events over REST. A row where REST disagrees with both the
     snapshot and everything replayed, whose change landed inside the window, is
     a change that never reached us.

A quiet window proves nothing: if nothing moved there was nothing to miss, and
the report says so rather than claiming a pass.

    fnox exec --profile prod -- uv run tools/bootstrap_gap.py --sport thoroughbred --country au
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from time import monotonic

from betwatch import APIConnectionError, Betwatch, Odds, RacingScope, ResyncRequired
from betwatch.types.stream import iter_odds

Key = tuple[str, str, str]


def _key(row: Odds) -> Key:
    return (row.key, row.entrant_id or "", row.source.id)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sport", action="append", choices=["thoroughbred", "greyhound", "harness"])
    p.add_argument("--country", action="append")
    p.add_argument("--watch", type=float, default=30.0, help="Seconds to follow after the read.")
    p.add_argument("--events", type=int, default=50, help="Events to verify over REST.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scope = RacingScope(sport=args.sport or ["thoroughbred"], country=args.country or ["au"])

    in_snapshot: dict[Key, Odds] = {}
    replayed: dict[Key, Odds] = {}
    from_window: list[tuple[Key, datetime]] = []

    with Betwatch() as client:
        print(f"host={client.base_url} scope={scope}", flush=True)

        opened = datetime.now(UTC)
        snap = client.snapshot(scope, limit=200)
        read_done = datetime.now(UTC)
        for row in snap.odds:
            in_snapshot[_key(row)] = row
        print(
            f"snapshot read in {(read_done - opened).total_seconds():.1f}s — "
            f"{len(snap.events)} races, {len(snap.odds)} prices",
            flush=True,
        )

        watch_started = monotonic()
        try:
            with client.follow(snap, reconnect=False) as live:
                for frame in live:
                    for row in iter_odds(frame):
                        replayed[_key(row)] = row
                        if row.updated_at and opened <= row.updated_at <= read_done:
                            from_window.append((_key(row), row.updated_at))
                    if monotonic() - watch_started > args.watch:
                        break
        except (APIConnectionError, ResyncRequired) as exc:
            # A rolling deploy cuts in-flight streams on this cluster. Resuming
            # from the cursor is the contract; for this test it just ends early.
            print(f"stream ended early: {type(exc).__name__}", flush=True)

        event_ids = sorted({row.event_id for row in in_snapshot.values()})[: args.events]
        rest: dict[Key, Odds] = {}
        for start in range(0, len(event_ids), 50):
            for row in client.odds.iter(event=event_ids[start : start + 50]):
                rest[_key(row)] = row
        print(f"rest verified {len(rest)} rows across {len(event_ids)} events", flush=True)

    missed: list[tuple[Key, float | None, float | None, datetime]] = []
    moved_after = 0
    for key, current in rest.items():
        known = replayed.get(key) or in_snapshot.get(key)
        if known is None or current.price == known.price:
            continue
        changed_at = current.updated_at
        if changed_at is None:
            continue
        if opened <= changed_at <= read_done:
            missed.append((key, known.price, current.price, changed_at))
        elif changed_at > read_done:
            moved_after += 1

    print("\n" + "=" * 72)
    print(f"read window            {(read_done - opened).total_seconds():.1f}s")
    print(f"prices in snapshot     {len(in_snapshot)}")
    print(f"prices replayed after  {len(replayed)}")
    print(f"REPLAYED FROM WINDOW   {len(from_window)}  <- the guarantee working")
    print(f"moved after the read   {moved_after}  (ordinary live movement)")
    print(f"MISSED CHANGES         {len(missed)}")
    for key, was, now, at in missed[:20]:
        print(f"  {key} snapshot={was} rest={now} changed_at={at.isoformat()}")

    if missed:
        print("\nVERDICT: changes published during the read did not reach the client.")
        return 2
    observed = len(from_window) + moved_after
    if not observed:
        print(
            "\nVERDICT: inconclusive — nothing moved during or after the read, so there"
            "\nwas nothing to miss. Re-run while racing is live."
        )
        return 0
    print(f"\nVERDICT: no missed changes, against {observed} observed moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
