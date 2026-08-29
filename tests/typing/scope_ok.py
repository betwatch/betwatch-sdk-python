from datetime import UTC, datetime

from betwatch import RacingScope, Sports

RacingScope(
    sport=[Sports.THOROUGHBRED, Sports.GREYHOUND],
    country="au",
    market="win",
    start_from=datetime.now(UTC),
)
