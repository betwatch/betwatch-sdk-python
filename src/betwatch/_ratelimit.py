from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .types.enums import BudgetHeaders


def _int(headers: Any, name: str) -> int | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _timestamp(headers: Any, name: str) -> datetime | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class RateLimit:
    """The two budgets, as reported on the last response.

    The short window (`limit`/`remaining`/`reset`) is per account per request
    class over a rolling minute: 300/min for discovery, 120/min for prices and
    event snapshots, 30/min for the catalogue. `reset` is seconds until it is
    full again.

    The monthly quota (`monthly_*`) prices how much data you take rather than
    how fast you ask, and `monthly_reset` is the absolute instant it refills —
    possibly weeks away, which is why `quota_exceeded` is never retried.

    Header names come from `BudgetHeaders`, which is reconciled against the
    contract in `tests/test_contract_spec.py`.
    """

    limit: int | None = None
    remaining: int | None = None
    reset: int | None = None
    monthly_limit: int | None = None
    monthly_used: int | None = None
    monthly_remaining: int | None = None
    monthly_reset: datetime | None = None

    @classmethod
    def from_headers(cls, headers: Any) -> RateLimit | None:
        """Parse the budget headers, or None when the response carried none."""
        limits = cls(
            limit=_int(headers, BudgetHeaders.LIMIT),
            remaining=_int(headers, BudgetHeaders.REMAINING),
            reset=_int(headers, BudgetHeaders.RESET),
            monthly_limit=_int(headers, BudgetHeaders.MONTHLY_LIMIT),
            monthly_used=_int(headers, BudgetHeaders.MONTHLY_USED),
            monthly_remaining=_int(headers, BudgetHeaders.MONTHLY_REMAINING),
            monthly_reset=_timestamp(headers, BudgetHeaders.MONTHLY_RESET),
        )
        return limits if limits.reported else None

    @property
    def reported(self) -> bool:
        """True when the response carried at least one budget header."""
        return any(getattr(self, field) is not None for field in self.__dataclass_fields__)
