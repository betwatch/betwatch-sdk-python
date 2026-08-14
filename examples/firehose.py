"""All-code firehose. Resume from the last SSE cursor.

First run snapshots quietly, then prints live ticks only. Unchanged
republishes are dropped. Pass --verbose to dump every frame.

    fnox exec --profile prod -- uv run examples/firehose.py --reset-all-cursors
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

import httpx

from betwatch import (
    APIStatusError,
    Betwatch,
    CoverageFrame,
    EntrantFrame,
    EventFrame,
    OddsFrame,
    ReadyFrame,
    ResyncRequired,
    SyncFrame,
)


def _ts() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cursor_path(base_url: str) -> Path:
    host = urlparse(base_url).netloc.replace(":", "_") or "default"
    return Path(f".firehose-cursor-{host}")


def _reset_cursors(target: Path | None, *, all_hosts: bool) -> None:
    removed = 0
    if all_hosts:
        for path in Path(".").glob(".firehose-cursor*"):
            path.unlink(missing_ok=True)
            removed += 1
    else:
        if target is not None:
            target.unlink(missing_ok=True)
            removed += 1
        Path(".firehose-cursor").unlink(missing_ok=True)
        removed += 1
    print(_ts(), "reset-cursor", "all" if all_hosts else "host", "files", removed, flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Betwatch public /v1 stream firehose")
    parser.add_argument(
        "--reset-cursor",
        action="store_true",
        help="Drop the saved cursor for this API host and snapshot from scratch.",
    )
    parser.add_argument(
        "--reset-all-cursors",
        action="store_true",
        help="Drop every .firehose-cursor* file (local, prod, …).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every snapshot and unchanged frame.",
    )
    return parser.parse_args(argv)


def _odds_delta(prev: float | None, price: float | None) -> str:
    if prev is None:
        return "new"
    if prev == price:
        return "same"
    return f"{prev}->{price}"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    now = datetime.now(UTC)
    start_from = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    start_to = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    last_price: dict[tuple[str, str, str, str], float | None] = {}
    last_event: dict[str, str] = {}
    last_entrant: dict[str, tuple[bool, str]] = {}
    last_coverage: dict[tuple[str, str, str], str] = {}
    with Betwatch() as client:
        cursor_file = _cursor_path(client.base_url)
        if args.reset_cursor or args.reset_all_cursors:
            _reset_cursors(cursor_file, all_hosts=args.reset_all_cursors)
        last = cursor_file.read_text().strip() if cursor_file.exists() else None
        live = bool(last)
        print(_ts(), "connect", client.base_url, "cursor", bool(last), flush=True)
        while True:
            snap_counts: Counter[str] = Counter()
            snap_sources: Counter[str] = Counter()
            try:
                snapshot = "none" if last else "full"
                print(_ts(), "open", snapshot, flush=True)
                with client.stream(
                    sport=["thoroughbred", "greyhound", "harness"],
                    country="au",
                    start_from=start_from,
                    start_to=start_to,
                    snapshot=snapshot,
                    cursor=last,
                ) as stream:
                    for frame in stream:
                        ts = _ts()
                        if frame.cursor:
                            last = frame.cursor
                        if isinstance(frame, ReadyFrame):
                            print(ts, "ready", "live" if live else "snapshot", flush=True)
                        elif isinstance(frame, SyncFrame):
                            live = True
                            if last:
                                cursor_file.write_text(last)
                            parts = [f"{name}={snap_counts[name]}" for name in ("event", "entrant", "odds", "coverage") if snap_counts[name]]
                            sources = len(snap_sources)
                            print(
                                ts,
                                "sync",
                                *parts,
                                f"sources={sources}" if sources else "",
                                "— ticks after this are live",
                                flush=True,
                            )
                        elif isinstance(frame, OddsFrame):
                            q = frame.data
                            key = (q.event_id, q.entrant_id or "", q.source.id, q.market_id)
                            prev = last_price.get(key)
                            last_price[key] = q.price
                            delta = _odds_delta(prev, q.price)
                            if not live:
                                snap_counts["odds"] += 1
                                snap_sources[q.source.id] += 1
                                if not args.verbose:
                                    continue
                            elif not args.verbose and delta == "same":
                                continue
                            print(
                                ts,
                                "odds",
                                q.source.id,
                                q.price,
                                delta,
                                q.event_id,
                                q.entrant_id,
                                flush=True,
                            )
                        elif isinstance(frame, EventFrame):
                            ev = frame.data
                            prev_status = last_event.get(ev.id)
                            last_event[ev.id] = ev.status
                            if not live:
                                snap_counts["event"] += 1
                                if not args.verbose:
                                    continue
                            elif not args.verbose and prev_status == ev.status:
                                continue
                            print(ts, "event", ev.id, ev.status, ev.start_at, flush=True)
                        elif isinstance(frame, EntrantFrame):
                            runner = frame.data
                            mark = "scr" if runner.scratched else runner.entry_state
                            prev_mark = last_entrant.get(runner.id)
                            last_entrant[runner.id] = (runner.scratched, runner.entry_state)
                            if not live:
                                snap_counts["entrant"] += 1
                                if not args.verbose:
                                    continue
                            elif not args.verbose and prev_mark == (runner.scratched, runner.entry_state):
                                continue
                            print(
                                ts,
                                "entrant",
                                runner.event_id,
                                f"#{runner.number}",
                                runner.name,
                                mark,
                                flush=True,
                            )
                        elif isinstance(frame, CoverageFrame):
                            c = frame.data
                            done = "complete" if c.complete else "partial"
                            cov_key = (c.event_id, c.market_id, c.source_id)
                            prev_state = last_coverage.get(cov_key)
                            last_coverage[cov_key] = c.state
                            if not live:
                                snap_counts["coverage"] += 1
                                snap_sources[c.source_id] += 1
                                if not args.verbose:
                                    continue
                            elif not args.verbose and prev_state == c.state:
                                continue
                            print(
                                ts,
                                "coverage",
                                c.source_id,
                                c.event_id,
                                c.market_id,
                                c.state,
                                done,
                                flush=True,
                            )
                        else:
                            print(ts, frame.type, flush=True)
            except (ResyncRequired, APIStatusError) as exc:
                if isinstance(exc, APIStatusError) and exc.status_code != 409:
                    raise
                last = None
                live = False
                last_price.clear()
                last_event.clear()
                last_entrant.clear()
                last_coverage.clear()
                cursor_file.unlink(missing_ok=True)
                reason = getattr(exc, "reason", None) or getattr(exc, "code", None) or "resync"
                print(_ts(), "resync", reason, "— dropping cursor, snapshot=full next", flush=True)
            except httpx.TransportError as exc:
                print(_ts(), "disconnected", type(exc).__name__, flush=True)
                sleep(1)
            except KeyboardInterrupt:
                if last:
                    cursor_file.write_text(last)
                print(_ts(), "stopped", flush=True)
                return


if __name__ == "__main__":
    main()
