from __future__ import annotations

from datetime import datetime

from .common import Model
from .enums import CoverageBookStatus, CoverageState, MarketKey


class CoverageBookPrice(Model):
    """One active entrant's price at the moment the book first became full."""

    entrant_id: str
    price: float
    observed_at: datetime


class CoverageBook(Model):
    """How much of a race one source has priced, counted over active entrants.

    - `status`: `"unpriced"` (no active entrant priced), `"partial"`, or `"full"`
      (every active entrant has a current price).
    - `active`: entrants not scratched, not a vacant box, and not a reserve that
      has not taken a box.
    - `priced`: active entrants with a current price from this source.
    - `full_at`: when the book first became full. Set once; a later scratching
      or suspension does not move it.
    - `first_full`: every active entrant's price at `full_at` — the first full
      card. Set with `full_at` and never changes.
    """

    status: CoverageBookStatus
    active: int
    priced: int
    full_at: datetime | None = None
    first_full: list[CoverageBookPrice] | None = None


class Coverage(Model):
    """One source's coverage of one race market.

    `book` says how many runners are priced; read `book.status` for "is the
    card full". On the stream a price frame always arrives before the coverage
    frame whose `book` it completed, so the first coverage frame with
    `book.status == "full"` means you already hold every price in it.

    `complete` is **deprecated**: it only means the source's last scan was a
    full scan, not that every runner is priced. Use `book.status`.
    """

    event_id: str
    key: MarketKey
    source_id: str
    state: CoverageState
    complete: bool  # deprecated: last scan was a full scan; use book.status
    places_paid: int | None = None
    observed_at: datetime | None = None
    book: CoverageBook | None = None
