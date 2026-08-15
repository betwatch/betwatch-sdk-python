"""Closed public vocabularies.

Field types are these Literals so `event.status == "resulted"` is a type
error (`final` is the public value). Named members exist for hand-written
code and autocomplete: `event.status == EventStatuses.OPEN`.
"""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

Sport: TypeAlias = Literal["thoroughbred", "greyhound", "harness"]


class Sports:
    THOROUGHBRED: Final[Sport] = "thoroughbred"
    GREYHOUND: Final[Sport] = "greyhound"
    HARNESS: Final[Sport] = "harness"


EventStatus: TypeAlias = Literal[
    "scheduled",
    "open",
    "in_progress",
    "closed",
    "interim",
    "final",
    "abandoned",
    "cancelled",
    "postponed",
    "unknown",
]


class EventStatuses:
    SCHEDULED: Final[Literal["scheduled"]] = "scheduled"
    OPEN: Final[Literal["open"]] = "open"
    IN_PROGRESS: Final[Literal["in_progress"]] = "in_progress"
    CLOSED: Final[Literal["closed"]] = "closed"
    INTERIM: Final[Literal["interim"]] = "interim"
    FINAL: Final[Literal["final"]] = "final"
    ABANDONED: Final[Literal["abandoned"]] = "abandoned"
    CANCELLED: Final[Literal["cancelled"]] = "cancelled"
    POSTPONED: Final[Literal["postponed"]] = "postponed"
    UNKNOWN: Final[Literal["unknown"]] = "unknown"


LIVE_EVENT_STATUSES: frozenset[EventStatus] = frozenset(
    {
        EventStatuses.SCHEDULED,
        EventStatuses.OPEN,
        EventStatuses.IN_PROGRESS,
        EventStatuses.CLOSED,
        EventStatuses.INTERIM,
    }
)

SETTLED_EVENT_STATUSES: frozenset[EventStatus] = frozenset(
    {
        EventStatuses.FINAL,
        EventStatuses.ABANDONED,
        EventStatuses.CANCELLED,
        EventStatuses.POSTPONED,
        EventStatuses.UNKNOWN,
    }
)

ResultState: TypeAlias = Literal["provisional", "final"]


class ResultStates:
    PROVISIONAL: Final[ResultState] = "provisional"
    FINAL: Final[ResultState] = "final"


EntryState: TypeAlias = Literal["listed", "omitted"]


class EntryStates:
    LISTED: Final[EntryState] = "listed"
    OMITTED: Final[EntryState] = "omitted"


SourceKind: TypeAlias = Literal["bookmaker", "tote", "exchange"]


class SourceKinds:
    BOOKMAKER: Final[SourceKind] = "bookmaker"
    TOTE: Final[SourceKind] = "tote"
    EXCHANGE: Final[SourceKind] = "exchange"


CompetitorKind: TypeAlias = Literal["animal"]


class CompetitorKinds:
    ANIMAL: Final[CompetitorKind] = "animal"


MarketKey: TypeAlias = Literal["win", "place"]


class MarketKeys:
    WIN: Final[MarketKey] = "win"
    PLACE: Final[MarketKey] = "place"


MarketState: TypeAlias = Literal["unsettled", "settled", "void", "unknown"]


class MarketStates:
    UNSETTLED: Final[MarketState] = "unsettled"
    SETTLED: Final[MarketState] = "settled"
    VOID: Final[MarketState] = "void"
    UNKNOWN: Final[MarketState] = "unknown"


MarketPeriod: TypeAlias = Literal["full"]


class MarketPeriods:
    FULL: Final[MarketPeriod] = "full"


OutcomeKey: TypeAlias = Literal["entrant"]


class OutcomeKeys:
    ENTRANT: Final[OutcomeKey] = "entrant"


OutcomeState: TypeAlias = Literal["unsettled", "winner", "loser", "void", "unknown"]


class OutcomeStates:
    UNSETTLED: Final[OutcomeState] = "unsettled"
    WINNER: Final[OutcomeState] = "winner"
    LOSER: Final[OutcomeState] = "loser"
    VOID: Final[OutcomeState] = "void"
    UNKNOWN: Final[OutcomeState] = "unknown"


OddsState: TypeAlias = Literal["available", "suspended", "withdrawn", "settled", "unknown"]


class OddsStates:
    AVAILABLE: Final[OddsState] = "available"
    SUSPENDED: Final[OddsState] = "suspended"
    WITHDRAWN: Final[OddsState] = "withdrawn"
    SETTLED: Final[OddsState] = "settled"
    UNKNOWN: Final[OddsState] = "unknown"


CoverageState: TypeAlias = Literal["unknown", "priced", "unpriced"]


class CoverageStates:
    UNKNOWN: Final[CoverageState] = "unknown"
    PRICED: Final[CoverageState] = "priced"
    UNPRICED: Final[CoverageState] = "unpriced"


ExchangeMarketState: TypeAlias = Literal["open", "suspended", "closed", "inactive", "unknown"]


class ExchangeMarketStates:
    OPEN: Final[ExchangeMarketState] = "open"
    SUSPENDED: Final[ExchangeMarketState] = "suspended"
    CLOSED: Final[ExchangeMarketState] = "closed"
    INACTIVE: Final[ExchangeMarketState] = "inactive"
    UNKNOWN: Final[ExchangeMarketState] = "unknown"


ExchangeOutcomeState: TypeAlias = Literal["active", "removed", "winner", "loser", "closed", "unknown"]


class ExchangeOutcomeStates:
    ACTIVE: Final[ExchangeOutcomeState] = "active"
    REMOVED: Final[ExchangeOutcomeState] = "removed"
    WINNER: Final[ExchangeOutcomeState] = "winner"
    LOSER: Final[ExchangeOutcomeState] = "loser"
    CLOSED: Final[ExchangeOutcomeState] = "closed"
    UNKNOWN: Final[ExchangeOutcomeState] = "unknown"


Surface: TypeAlias = Literal["turf", "all_weather", "dirt", "sand", "synthetic"]


class Surfaces:
    TURF: Final[Surface] = "turf"
    ALL_WEATHER: Final[Surface] = "all_weather"
    DIRT: Final[Surface] = "dirt"
    SAND: Final[Surface] = "sand"
    SYNTHETIC: Final[Surface] = "synthetic"


DividendPool: TypeAlias = Literal[
    "win", "place", "quinella", "exacta", "duet", "trifecta", "first4"
]


class DividendPools:
    WIN: Final[DividendPool] = "win"
    PLACE: Final[DividendPool] = "place"
    QUINELLA: Final[DividendPool] = "quinella"
    EXACTA: Final[DividendPool] = "exacta"
    DUET: Final[DividendPool] = "duet"
    TRIFECTA: Final[DividendPool] = "trifecta"
    FIRST4: Final[DividendPool] = "first4"


IncludeFlag: TypeAlias = Literal["coverage", "history", "racing"]


class IncludeFlags:
    COVERAGE: Final[IncludeFlag] = "coverage"
    HISTORY: Final[IncludeFlag] = "history"
    RACING: Final[IncludeFlag] = "racing"


SnapshotMode: TypeAlias = Literal["full", "none"]


class SnapshotModes:
    FULL: Final[SnapshotMode] = "full"
    NONE: Final[SnapshotMode] = "none"
