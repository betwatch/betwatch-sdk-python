"""Public `/v1` REST + SSE client. This is 2.0.0b1 — not the GraphQL 1.x SDK.

Preferred workflow for agents and humans:

```python
from betwatch import Betwatch, EventStatuses, OddsFrame

with Betwatch() as client:
    page = client.events.list(sport="thoroughbred", country="au", limit=5)
    with client.watch(page[0].id) as live:
        print(live.snapshot.event.name)
        for frame in live:
            if isinstance(frame, OddsFrame):
                if live.snapshot.event.status == EventStatuses.OPEN:
                    print(frame.data.source.id, frame.data.price)
```

There is no `get_races`. Events are races; entrants are runners.
"""

from .__about__ import __version__
from ._changes import ChangeTracker
from ._client import AsyncBetwatch, AsyncWatch, Betwatch, Watch
from ._exceptions import (
    AccountDisabledError,
    APIConnectionError,
    APIDecodeError,
    APIKeyNotSetError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BetwatchError,
    BootstrapFailedError,
    CredentialInQueryError,
    CursorError,
    EntitlementEmptyError,
    FieldError,
    FilterRequiredError,
    InternalServerError,
    MethodNotAllowedError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
    ResyncRequired,
    ServiceUnavailableError,
    StreamDecodeError,
    StreamLimitError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from ._progress import StreamProgress, print_progress
from ._ratelimit import RateLimit
from .types import (
    BudgetHeaders,
    Competitor,
    Coverage,
    CoverageFrame,
    Entrant,
    EntrantFrame,
    EntrantPage,
    ErrorCodes,
    Event,
    EventFrame,
    EventPage,
    EventSnapshot,
    EventStatus,
    EventStatuses,
    Market,
    MarketFrame,
    Meeting,
    Odds,
    OddsFrame,
    OddsPage,
    OddsSetFrame,
    Outcome,
    ReadyFrame,
    ScopeSnapshot,
    Source,
    Sport,
    Sports,
    StreamFrame,
    SyncFrame,
    UnknownFrame,
    Venue,
    to_dict,
    to_json,
    to_records,
)

__all__ = [
    "BootstrapFailedError",
    "ScopeSnapshot",
    "ChangeTracker",
    "print_progress",
    "StreamProgress",
    "CursorError",
    "BudgetHeaders",
    "UnsupportedMediaTypeError",
    "StreamLimitError",
    "ServiceUnavailableError",
    "MethodNotAllowedError",
    "CredentialInQueryError",
    "RateLimit",
    "QuotaExceededError",
    "FieldError",
    "ErrorCodes",
    "EntitlementEmptyError",
    "AccountDisabledError",
    "APIDecodeError",
    "APIConnectionError",
    "APIKeyNotSetError",
    "APIStatusError",
    "APITimeoutError",
    "AsyncBetwatch",
    "AsyncWatch",
    "AuthenticationError",
    "BadRequestError",
    "Betwatch",
    "BetwatchError",
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
    "EventStatus",
    "EventStatuses",
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
    "Sport",
    "Sports",
    "StreamFrame",
    "StreamDecodeError",
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
