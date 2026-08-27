"""Drop republished state that has not actually changed.

The stream republishes current state — on bootstrap, on reconnect, and when a
source re-asserts a price it already sent. Almost every consumer wants "tell me
what moved", and writing that by hand means knowing which field of each frame
counts as its state: a price for odds, a status for an event, scratched plus
entry state for a runner. That knowledge belongs here, not in every caller.

    tracker = ChangeTracker()
    for frame in stream:
        if tracker.changed(frame):
            ...  # first sight of this thing, or a real change

`changed()` also accepts an `Odds` row, so a caller unpacking `odds_set` with
`iter_odds()` can filter per row rather than per frame.
"""

from __future__ import annotations

from typing import Any

from .types.coverage import Coverage
from .types.entrant import Entrant
from .types.odds import Odds
from .types.stream import (
    CoverageFrame,
    EntrantFrame,
    EventFrame,
    OddsFrame,
    StreamEvent,
    StreamFrame,
)

_Key = tuple[str, ...]


def _identity(item: Any) -> tuple[_Key, Any] | None:
    """The thing's identity, and the state that makes it 'changed'."""
    if isinstance(item, Odds):
        return (("odds", item.id), (item.price, item.state))
    if isinstance(item, StreamEvent):
        return ("event", item.id), (item.status, item.start_at)
    if isinstance(item, Entrant):
        return ("entrant", item.id), (item.scratched, item.entry_state)
    if isinstance(item, Coverage):
        return (
            ("coverage", item.event_id, item.key, item.places_paid, item.source_id),
            (item.state, item.complete),
        )
    return None


def _payload(item: Any) -> Any:
    if isinstance(
        item,
        (OddsFrame, EventFrame, EntrantFrame, CoverageFrame),
    ):
        return item.data
    return item


class ChangeTracker:
    """Remembers the last state of everything it has been shown.

    Not thread-safe, and unbounded by design: a raceday's worth of keys is
    small, and forgetting one would turn a republish into a false "changed".
    Call `clear()` after a resync, where the SDK's state is no longer valid.
    """

    def __init__(self) -> None:
        self._seen: dict[_Key, Any] = {}

    def changed(self, item: StreamFrame | Odds | Any) -> bool:
        """True if this is new or its state moved. Unknown kinds are always new."""
        identified = _identity(_payload(item))
        if identified is None:
            return True
        key, value = identified
        previous = self._seen.get(key, _MISSING)
        self._seen[key] = value
        return previous is _MISSING or previous != value

    def clear(self) -> None:
        """Forget everything. Use on resync, when replayed state is unreliable."""
        self._seen.clear()

    def __len__(self) -> int:
        return len(self._seen)


_MISSING = object()
