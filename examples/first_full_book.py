"""Capture the first full Sportsbet win card for every greyhound race in a day.

A race's book is "full" when every active runner (not scratched, not a vacant
box, not an un-boxed reserve) has a price from the source. This records each
race once, at the moment its book first became full.

Two ways, both shown here:

* After the fact: a REST snapshot already carries `coverage.book.first_full`,
  every runner's price at `book.full_at`. Nothing to follow.
* Live: snapshot the day, then follow it. Within
  one race a price frame always arrives before the coverage frame whose book it
  completed, so on the first coverage frame with `book.status == "full"` the
  prices already held *are* the full card (and `book.first_full` says the same).

    fnox exec --profile prod -- uv run examples/first_full_book.py
    fnox exec --profile prod -- uv run examples/first_full_book.py --date 2026-10-30 --after
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from betwatch import (
    Betwatch,
    Coverage,
    CoverageBookStatuses,
    CoverageFrame,
    RacingScope,
    ResyncRequired,
    ScopeSnapshot,
)
from betwatch.types.stream import iter_odds

SYDNEY = ZoneInfo("Australia/Sydney")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="First full win card per race for one day")
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(SYDNEY).date())
    parser.add_argument("--source", default="sportsbet")
    parser.add_argument(
        "--sport", choices=["thoroughbred", "greyhound", "harness"], default="greyhound"
    )
    parser.add_argument(
        "--after", action="store_true", help="Read book.firstFull from REST only; do not follow."
    )
    return parser.parse_args(argv)


def day_scope(args: argparse.Namespace) -> RacingScope:
    start = datetime.combine(args.date, time.min, SYDNEY)
    return RacingScope(
        sport=args.sport,
        source=args.source,
        key="win",
        start_from=start,
        start_to=start + timedelta(days=1),
    )


def snapshot_day(
    client: Betwatch, scope: RacingScope, resync_token: str | None = None
) -> tuple[ScopeSnapshot, list[ScopeSnapshot]]:
    """Every page of the day. Each page carries the same `stream` to follow."""
    first = client.snapshot(scope, resync_token=resync_token)
    pages = [first]
    while pages[-1].next:
        pages.append(client.snapshot_page(after=pages[-1].next))
    return first, pages


def record(row: Coverage, card: dict[str, float], how: str) -> None:
    book = row.book
    assert book is not None
    if book.first_full:  # the server's own record of the first full card
        card = {p.entrant_id: p.price for p in book.first_full}
    print(
        json.dumps(
            {
                "event": row.event_id,
                "source": row.source_id,
                "fullAt": book.full_at.isoformat() if book.full_at else None,
                "via": how,
                "prices": card,
            }
        ),
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scope = day_scope(args)
    recorded: set[str] = set()
    races: set[str] = set()
    # event -> entrant -> latest win price from the source
    prices: dict[str, dict[str, float]] = {}

    def absorb(pages: list[ScopeSnapshot]) -> None:
        for page in pages:
            races.update(event.id for event in page.events)
            for quote in page.odds:
                if quote.entrant_id and quote.price is not None:
                    prices.setdefault(quote.event_id, {})[quote.entrant_id] = quote.price
            for row in page.coverage:
                book = row.book
                if book and book.status == CoverageBookStatuses.FULL:
                    if row.event_id not in recorded:
                        recorded.add(row.event_id)
                        record(row, prices.get(row.event_id, {}), "snapshot")

    with Betwatch() as client:
        first, pages = snapshot_day(client, scope)
        absorb(pages)
        if args.after:
            return
        while not races <= recorded:
            try:
                # Only prices and coverage: event and entrant frames are skipped
                # by the server and still advance the cursor. `follow()` sends
                # the same request as `first.stream.url`.
                with client.follow(first) as live:
                    for frame in live:
                        for quote in iter_odds(frame):
                            if quote.entrant_id and quote.price is not None:
                                prices.setdefault(quote.event_id, {})[quote.entrant_id] = (
                                    quote.price
                                )
                        if not isinstance(frame, CoverageFrame):
                            continue
                        row = frame.data
                        book = row.book
                        if book is None or book.status != CoverageBookStatuses.FULL:
                            continue
                        if row.event_id in recorded:
                            continue
                        recorded.add(row.event_id)
                        # Price frames arrive before the coverage frame they
                        # completed, so every price in this book is already held.
                        record(row, dict(prices.get(row.event_id, {})), "stream")
                        if races <= recorded:
                            return
            except ResyncRequired as resync:
                # Routine (a worker restart broadcasts one). The old cursor is
                # dead: snapshot again (passing the resync token, when the frame
                # carries one, makes it free) and follow the new `stream`. Races
                # that went full meanwhile come from `book.first_full` there.
                first, pages = snapshot_day(client, scope, resync.resync_token)
                absorb(pages)
            except KeyboardInterrupt:
                return


if __name__ == "__main__":
    main()
