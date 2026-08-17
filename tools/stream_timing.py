#!/usr/bin/env python
"""Measure how long `/v1/stream` takes to bootstrap, for one filter scope.

Built for the platform team to re-run against a build before launch and keep as
a regression check afterwards. It reports the three numbers that matter and, in
particular, the silence: how long the connection sits with nothing on it before
the first data frame arrives.

    fnox exec --profile prod -- uv run tools/stream_timing.py
    fnox exec --profile prod -- uv run tools/stream_timing.py --sport thoroughbred --country au
    fnox exec --profile prod -- uv run tools/stream_timing.py --json --require-sync 60

Exits non-zero when `--require-sync` is given and the bootstrap does not
complete inside it, so this works as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from time import monotonic

from betwatch import Betwatch, ReadyFrame, StreamProgress, SyncFrame
from betwatch.types.stream import frame_name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sport", action="append", choices=["thoroughbred", "greyhound", "harness"])
    p.add_argument("--country", action="append")
    p.add_argument("--event", action="append")
    p.add_argument("--timeout", type=float, default=180.0, help="Give up after this long.")
    p.add_argument(
        "--require-sync",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Exit 1 unless the bootstrap completes within SECONDS.",
    )
    p.add_argument("--json", action="store_true", help="Emit one JSON object instead of a report.")
    p.add_argument("--quiet", action="store_true", help="Suppress the per-interval progress lines.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    counts: Counter[str] = Counter()
    pings = 0
    started = monotonic()
    t_ready = t_first = t_sync = None
    timed_out = False

    def report(progress: StreamProgress) -> None:
        nonlocal pings
        pings = progress.pings
        if not args.quiet and not args.json:
            print(progress, file=sys.stderr, flush=True)

    with Betwatch() as client:
        scope = {
            "sport": args.sport or ["thoroughbred", "greyhound", "harness"],
            "country": args.country,
            "event": args.event,
        }
        if not args.json:
            print(
                f"host={client.base_url} scope={ {k: v for k, v in scope.items() if v} }",
                file=sys.stderr,
                flush=True,
            )
        with client.stream(
            **{k: v for k, v in scope.items() if v},
            snapshot="full",
            reconnect=False,
            progress=report,
        ) as stream:
            for frame in stream:
                now = monotonic() - started
                if isinstance(frame, ReadyFrame):
                    t_ready = now
                    continue
                if isinstance(frame, SyncFrame):
                    t_sync = now
                    break
                counts[frame_name(frame)] += 1
                if t_first is None:
                    t_first = now
                if now > args.timeout:
                    timed_out = True
                    break

    frames = sum(counts.values())
    elapsed = t_sync if t_sync is not None else monotonic() - started
    result = {
        "host": client.base_url,
        "scope": {k: v for k, v in scope.items() if v},
        "ready_s": t_ready and round(t_ready, 2),
        "first_frame_s": t_first and round(t_first, 2),
        # The number to watch: dead air between the connection opening and any data.
        "silence_s": round((t_first or elapsed) - (t_ready or 0.0), 2),
        "sync_s": t_sync and round(t_sync, 2),
        "frames": frames,
        "frames_per_s": round(frames / elapsed, 1) if elapsed > 0 else None,
        "keepalives_during_bootstrap": pings,
        "counts": dict(counts),
        "timed_out": timed_out,
    }

    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"\nready       {result['ready_s']}s"
            f"\nfirst frame {result['first_frame_s']}s"
            f"\nsilence     {result['silence_s']}s  <- dead air after ready"
            f"\nsync        {result['sync_s']}s"
            f"\nframes      {frames} at {result['frames_per_s']}/s  {dict(counts)}"
            f"\nkeepalives  {pings} during bootstrap"
            + ("\nTIMED OUT before sync" if timed_out else "")
        )

    if args.require_sync is not None and (t_sync is None or t_sync > args.require_sync):
        got = "no sync" if t_sync is None else f"{t_sync:.1f}s"
        print(f"FAIL: bootstrap needed <= {args.require_sync}s, got {got}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
