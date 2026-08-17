"""All-code firehose. Resume from the last SSE cursor.

The first run takes a full snapshot, reporting progress while it arrives,
then prints live ticks only; unchanged republishes are dropped. Later runs
resume from the saved cursor and are live immediately.

Default scope is every sport in every country the key can see, which is the
slowest possible bootstrap: expect no frames at all for the first 20-45s while
the server builds the snapshot, then tens of thousands of rows. The wait and
the volume both scale with scope, and sport narrows it far more than country
does on an AU-weighted key.

    fnox exec --profile prod -- uv run examples/firehose.py --reset-all-cursors
    fnox exec --profile prod -- uv run examples/firehose.py --sport thoroughbred --country au
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

import httpx

from betwatch import (
    APIStatusError,
    Betwatch,
    ChangeTracker,
    CoverageFrame,
    EntrantFrame,
    EventFrame,
    OddsFrame,
    OddsSetFrame,
    ReadyFrame,
    ResyncRequired,
    SyncFrame,
    print_progress,
)
from betwatch.types.stream import iter_odds


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
    parser.add_argument(
        "--country",
        action="append",
        default=None,
        help="Optional country filter (repeatable). Default: every country the key can see.",
    )
    parser.add_argument(
        "--sport",
        action="append",
        choices=["thoroughbred", "greyhound", "harness"],
        default=None,
        help="Sport filter (repeatable). Default: all three, which is the slowest bootstrap.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    changes = ChangeTracker()
    with Betwatch() as client:
        cursor_file = _cursor_path(client.base_url)
        if args.reset_cursor or args.reset_all_cursors:
            _reset_cursors(cursor_file, all_hosts=args.reset_all_cursors)
        last = cursor_file.read_text().strip() if cursor_file.exists() else None
        live = bool(last)
        countries = ",".join(args.country) if args.country else "all-countries"
        sports = ",".join(args.sport) if args.sport else "all-sports"
        print(
            _ts(),
            "connect",
            client.base_url,
            "cursor",
            bool(last),
            "scope",
            f"{sports}/{countries}",
            flush=True,
        )
        while True:
            try:
                snapshot = "none" if last else "full"
                print(_ts(), "open", snapshot, flush=True)
                with client.stream(
                    sport=args.sport or ["thoroughbred", "greyhound", "harness"],
                    country=args.country,
                    snapshot=snapshot,
                    cursor=last,
                    progress=print_progress,
                ) as stream:
                    for frame in stream:
                        ts = _ts()
                        if frame.cursor:
                            last = frame.cursor
                        if isinstance(frame, ReadyFrame):
                            print(ts, "ready", "live" if live else "snapshot", flush=True)
                            continue
                        if isinstance(frame, SyncFrame):
                            live = True
                            if last:
                                cursor_file.write_text(last)
                            print(ts, "sync — ticks after this are live", flush=True)
                            continue
                        # The SDK knows what "changed" means per frame kind, so
                        # a republished price at the same number is dropped here.
                        if not args.verbose and not changes.changed(frame):
                            continue
                        if not live and not args.verbose:
                            continue  # bootstrap state; progress= already reports it

                        if isinstance(frame, (OddsFrame, OddsSetFrame)):
                            for q in iter_odds(frame):
                                if not args.verbose and not changes.changed(q):
                                    continue
                                print(
                                    ts,
                                    "odds",
                                    q.source.id,
                                    q.price,
                                    q.event_id,
                                    q.entrant_id,
                                    flush=True,
                                )
                        elif isinstance(frame, EventFrame):
                            ev = frame.data
                            print(ts, "event", ev.id, ev.status, ev.start_at, flush=True)
                        elif isinstance(frame, EntrantFrame):
                            runner = frame.data
                            mark = "scr" if runner.scratched else runner.entry_state
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
                            print(
                                ts,
                                "coverage",
                                c.source_id,
                                c.event_id,
                                c.market_id,
                                c.state,
                                "complete" if c.complete else "partial",
                                flush=True,
                            )
                        else:
                            print(ts, frame.type, flush=True)
            except (ResyncRequired, APIStatusError) as exc:
                if isinstance(exc, APIStatusError) and exc.status_code != 409:
                    raise
                last = None
                live = False
                changes.clear()
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
