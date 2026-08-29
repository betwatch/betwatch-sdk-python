#!/usr/bin/env python
"""Time how long it takes to start following a scope, and how often that fails.

Measures the path the contract now offers: read `GET /v2/events/snapshot`, then follow
the cursor it returned. An earlier version opened `snapshot=full`, which the
server refuses above an event, meeting or venue — it reported ten drops in ten
attempts that were really ten `422 filter_required`. That is the shape of tool
failure worth naming: a confident number measuring something that no longer
exists.

`--repeat N` runs N attempts and reports how many survived. In-flight streams on
this cluster are cut by rolling deployments — pods get a 30s grace period, so a
deploy severs every open SSE connection — so a drop rate here tracks deploy
activity rather than server health. Run it during a quiet window for the floor.

    fnox exec --profile prod -- uv run tools/stream_timing.py --sport thoroughbred --country au
    fnox exec --profile prod -- uv run tools/stream_timing.py --repeat 10 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from time import monotonic
from typing import Any

from betwatch import (
    APIConnectionError,
    Betwatch,
    RacingScope,
    ReadyFrame,
    ResyncRequired,
    StreamProgress,
)
from betwatch.types.stream import frame_name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sport", action="append", choices=["thoroughbred", "greyhound", "harness"])
    p.add_argument("--country", action="append")
    p.add_argument("--watch", type=float, default=30.0, help="Seconds to follow after attaching.")
    p.add_argument("--repeat", type=int, default=1, metavar="N", help="Attempts, for a drop rate.")
    p.add_argument("--require-attach", type=float, default=None, metavar="SECONDS")
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def _measure(args: argparse.Namespace) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    pings = 0
    started = monotonic()
    t_ready = t_first = None
    ended_early: str | None = None

    def report(progress: StreamProgress) -> None:
        nonlocal pings
        pings = progress.pings
        if not args.quiet and not args.json:
            print(progress, file=sys.stderr, flush=True)

    scope = RacingScope(sport=args.sport, country=args.country)
    with Betwatch() as client:
        if not args.json and not args.quiet:
            print(f"host={client.base_url} scope={scope}", file=sys.stderr, flush=True)
        snap = client.snapshot(scope, limit=200)
        t_snapshot = monotonic() - started
        try:
            with client.follow(snap, reconnect=False, progress=report) as live:
                for frame in live:
                    now = monotonic() - started
                    if isinstance(frame, ReadyFrame):
                        t_ready = now
                        continue
                    counts[frame_name(frame)] += 1
                    if t_first is None:
                        t_first = now
                    if now - (t_ready or t_snapshot) > args.watch:
                        break
        except (APIConnectionError, ResyncRequired) as exc:
            ended_early = f"{type(exc).__name__}: {exc}"
        base_url = client.base_url

    return {
        "host": base_url,
        "scope": {"sport": scope.sport, "country": scope.country},
        "snapshot_s": round(t_snapshot, 2),
        "races": len(snap.events),
        "prices": len(snap.odds),
        "attach_s": t_ready and round(t_ready, 2),
        "first_frame_s": t_first and round(t_first, 2),
        "frames": sum(counts.values()),
        "keepalives": pings,
        "counts": dict(counts),
        "ended_early": ended_early,
    }


def _once(args: argparse.Namespace) -> int:
    result = _measure(args)
    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"\nsnapshot    {result['snapshot_s']}s  "
            f"({result['races']} races, {result['prices']} prices)"
            f"\nattach      {result['attach_s']}s  <- ready on the stream"
            f"\nfirst frame {result['first_frame_s']}s"
            f"\nframes      {result['frames']}  {result['counts']}"
            f"\nkeepalives  {result['keepalives']}"
            + (f"\nENDED EARLY {result['ended_early']}" if result["ended_early"] else "")
        )
    attach = result["attach_s"]
    if args.require_attach is not None and (attach is None or attach > args.require_attach):
        got = "never attached" if attach is None else f"{attach:.1f}s"
        print(f"FAIL: attach needed <= {args.require_attach}s, got {got}", file=sys.stderr)
        return 1
    return 0


def _repeat(args: argparse.Namespace) -> int:
    drops: list[str] = []
    attached: list[float] = []
    for attempt in range(1, args.repeat + 1):
        print(f"--- attempt {attempt}/{args.repeat} ---", file=sys.stderr, flush=True)
        try:
            result = _measure(args)
        except Exception as exc:  # noqa: BLE001 - a failure is the measurement
            drops.append(f"{type(exc).__name__}: {exc}")
            print(f"  FAILED  {type(exc).__name__}", file=sys.stderr, flush=True)
            continue
        if result["ended_early"]:
            drops.append(result["ended_early"])
            print(f"  DROPPED {result['ended_early'][:70]}", file=sys.stderr, flush=True)
        else:
            attached.append(result["attach_s"])
            print(f"  ok, attached in {result['attach_s']}s", file=sys.stderr, flush=True)

    print(
        json.dumps(
            {
                "attempts": args.repeat,
                "survived": len(attached),
                "dropped": len(drops),
                "drop_rate": round(len(drops) / args.repeat, 3),
                "attach_seconds": attached,
                "failures": drops,
            }
        )
    )
    return 0 if not drops else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return _repeat(args) if args.repeat > 1 else _once(args)


if __name__ == "__main__":
    raise SystemExit(main())
