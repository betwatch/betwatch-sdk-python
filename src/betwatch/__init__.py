"""Public `/v1` REST + SSE client. This is 2.0.0b1 — not the GraphQL 1.x SDK.

Preferred workflow for agents and humans:

```python
from betwatch import Betwatch, OddsFrame

with Betwatch() as client:
    page = client.events.list(sport="thoroughbred", country="au", limit=5)
    with client.watch(page[0].id) as live:
        print(live.snapshot.event.name)
        for frame in live:
            if isinstance(frame, OddsFrame):
                print(frame.data.source.id, frame.data.price)
```

There is no `get_races`. Events are races; entrants are runners.
"""

from .__about__ import __version__
from ._client import AsyncBetwatch, AsyncWatch, Betwatch, Watch, connect, connect_async
from ._exceptions import (
    APIDecodeError,
    APIKeyNotSetError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    BetwatchError,
    FilterRequiredError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ResyncRequired,
    UnprocessableEntityError,
)
from .types import (
    Competitor,
    Coverage,
    CoverageFrame,
    Entrant,
    EntrantFrame,
    EntrantPage,
    Event,
    EventFrame,
    EventPage,
    EventSnapshot,
    Market,
    MarketFrame,
    Meeting,
    Odds,
    OddsFrame,
    OddsPage,
    OddsSetFrame,
    Outcome,
    ReadyFrame,
    Source,
    StreamFrame,
    SyncFrame,
    UnknownFrame,
    Venue,
    to_dict,
    to_json,
    to_records,
)

__all__ = [
    "APIDecodeError",
    "APIKeyNotSetError",
    "APIStatusError",
    "AsyncBetwatch",
    "AsyncWatch",
    "AuthenticationError",
    "BadRequestError",
    "Betwatch",
    "BetwatchError",
    "connect",
    "connect_async",
    "Competitor",
    "Coverage",
    "CoverageFrame",
    "Entrant",
    "EntrantFrame",
    "EntrantPage",
    "Event",
    "EventFrame",
    "EventPage",
    "EventSnapshot",
    "FilterRequiredError",
    "InternalServerError",
    "Market",
    "MarketFrame",
    "Meeting",
    "NotFoundError",
    "Odds",
    "OddsFrame",
    "OddsPage",
    "OddsSetFrame",
    "Outcome",
    "PermissionDeniedError",
    "RateLimitError",
    "ReadyFrame",
    "ResyncRequired",
    "Source",
    "StreamFrame",
    "SyncFrame",
    "UnprocessableEntityError",
    "UnknownFrame",
    "Venue",
    "Watch",
    "to_dict",
    "to_json",
    "to_records",
    "__version__",
]
