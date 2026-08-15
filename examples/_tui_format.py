from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from betwatch.types.event import Event
    from betwatch.types.venue import Venue

SPORTS = ("thoroughbred", "harness", "greyhound")
COUNTRIES = ("au", "nz")

SOURCE_ORDER = (
    "betfair",
    "sportsbet",
    "tab",
    "tab-nsw",
    "tab-qld",
    "tab-vic",
    "tab-wa",
    "ladbrokes",
    "neds",
    "bet365",
    "pointsbet",
    "unibet",
    "dabble",
    "palmerbet",
    "betright",
    "tabtouch",
    "betr",
    "playup",
    "boombet",
)

SOURCE_LABELS = {
    "betfair": "BF",
    "sportsbet": "SB",
    "tab": "TAB",
    "tab-nsw": "NSW",
    "tab-qld": "QLD",
    "tab-vic": "VIC",
    "tab-wa": "WA",
    "ladbrokes": "LAD",
    "neds": "NEDS",
    "bet365": "365",
    "pointsbet": "PB",
    "unibet": "UNI",
    "dabble": "DAB",
    "palmerbet": "PAL",
    "betright": "BR",
    "tabtouch": "TT",
    "betr": "BETR",
    "playup": "PU",
    "boombet": "BB",
}

SPORT_MARK = {
    "thoroughbred": "T",
    "harness": "H",
    "greyhound": "G",
}

_RACE_NUMBER = re.compile(r"\bR(?:ace\s*)?(\d+)\b", re.IGNORECASE)
_TRAILING_RACE = re.compile(r"\s*R(?:ace\s*)?\d+\s*$", re.IGNORECASE)

_CLOSED = frozenset({"final", "abandoned", "cancelled", "postponed"})


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def format_price(value: float | None) -> str:
    """Punter-facing decimal: 10.00 → 10, 2.40 → 2.4, 2.35 → 2.35."""
    if value is None:
        return "—"
    text = f"{value:.2f}"
    if text.endswith("00"):
        return text[:-3]
    if text.endswith("0"):
        return text[:-1]
    return text


def format_ttj(
    start: datetime,
    now: datetime,
    *,
    only_largest: bool = False,
) -> str:
    """Same shape as the web `calculateTimeToJump` helper."""
    delta = (aware(start) - aware(now)).total_seconds()
    sign = "-" if delta < 0 else ""
    remaining = abs(delta)
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)
    minutes = int((remaining % 3600) // 60)
    seconds = int(remaining % 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    if only_largest:
        return f"{sign}{parts[0]}"
    return sign + " ".join(parts)


def format_clock(start: datetime) -> str:
    local = aware(start).astimezone()
    return local.strftime("%H:%M")


def race_number(event: Event) -> int:
    number = event.racing.race_number
    if number:
        return number
    match = _RACE_NUMBER.search(event.name)
    return int(match.group(1)) if match else 0


def track_name(event: Event, venues: dict[str, Venue] | None = None) -> str:
    if venues and event.venue_id:
        venue = venues.get(event.venue_id)
        if venue and venue.name:
            return venue.name
    stripped = _TRAILING_RACE.sub("", event.name).strip()
    return stripped or event.name


def event_title(event: Event, venues: dict[str, Venue] | None = None) -> str:
    number = race_number(event)
    track = track_name(event, venues)
    return f"R{number} {track}" if number else track


def status_label(event: Event, now: datetime) -> str:
    status = event.status.lower()
    if status == "open":
        if aware(event.start_at) <= aware(now):
            return "NOW"
        return format_ttj(event.start_at, now, only_largest=True)
    labels = {
        "closed": "CLOSED",
        "interim": "INT",
        "final": "FIN",
        "abandoned": "ABD",
        "cancelled": "CAN",
        "postponed": "PPD",
    }
    return labels.get(status, status.upper())


def status_style(event: Event, now: datetime) -> str:
    status = event.status.lower()
    if status == "open":
        remaining = (aware(event.start_at) - aware(now)).total_seconds()
        if remaining <= 0:
            return "bold reverse #ff5d5d"
        if remaining <= 120:
            return "bold #ff5d5d"
        if remaining <= 600:
            return "bold #f5a524"
        return "bold #7ae0b8"
    if status == "closed":
        return "#c9b27c"
    if status == "interim":
        return "bold #f5a524"
    return "dim"


def source_label(source_id: str, name: str | None = None) -> str:
    if source_id in SOURCE_LABELS:
        return SOURCE_LABELS[source_id]
    if name:
        compact = re.sub(r"[^A-Za-z0-9]", "", name)
        return compact[:4].upper() or source_id[:4].upper()
    return source_id[:4].upper()


def source_sort_key(source_id: str) -> tuple[int, str]:
    try:
        return (SOURCE_ORDER.index(source_id), source_id)
    except ValueError:
        return (len(SOURCE_ORDER), source_id)


def sort_events(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda event: (aware(event.start_at), race_number(event), event.id))


def next_open(events: list[Event], now: datetime | None = None) -> Event | None:
    clock = aware(now or utcnow())
    for event in sort_events(events):
        if event.status.lower() == "open" and aware(event.start_at) >= clock:
            return event
    for event in sort_events(events):
        if event.is_open:
            return event
    return events[0] if events else None


def is_stale_finished(
    event: Event, now: datetime, *, grace: timedelta = timedelta(minutes=30)
) -> bool:
    if event.status.lower() not in _CLOSED:
        return False
    return aware(now) - aware(event.start_at) > grace


def date_bucket(start: datetime, now: datetime) -> str:
    local_start = aware(start).astimezone().date()
    today = aware(now).astimezone().date()
    delta = (local_start - today).days
    if delta <= -1:
        return "Earlier"
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    return local_start.strftime("%a %d %b")
