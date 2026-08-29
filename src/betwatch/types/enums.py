"""Closed public vocabularies.

Field types are these Literals so `event.status == "resulted"` is a type
error (`final` is the public value). Named members exist for hand-written
code and autocomplete: `event.status == EventStatuses.OPEN`.
"""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

RequestSport: TypeAlias = Literal["thoroughbred", "greyhound", "harness"]
Sport: TypeAlias = Literal["thoroughbred", "greyhound", "harness", "unknown"]


class Sports:
    THOROUGHBRED: Final[RequestSport] = "thoroughbred"
    GREYHOUND: Final[RequestSport] = "greyhound"
    HARNESS: Final[RequestSport] = "harness"
    UNKNOWN: Final[Sport] = "unknown"


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

ResultState: TypeAlias = Literal["provisional", "final", "unknown"]


class ResultStates:
    PROVISIONAL: Final[ResultState] = "provisional"
    FINAL: Final[ResultState] = "final"
    UNKNOWN: Final[ResultState] = "unknown"


EntryState: TypeAlias = Literal["listed", "omitted", "unknown"]


class EntryStates:
    LISTED: Final[EntryState] = "listed"
    OMITTED: Final[EntryState] = "omitted"
    UNKNOWN: Final[EntryState] = "unknown"


SourceKind: TypeAlias = Literal["bookmaker", "tote", "exchange", "unknown"]


class SourceKinds:
    BOOKMAKER: Final[SourceKind] = "bookmaker"
    TOTE: Final[SourceKind] = "tote"
    EXCHANGE: Final[SourceKind] = "exchange"
    UNKNOWN: Final[SourceKind] = "unknown"


CompetitorKind: TypeAlias = Literal["animal", "unknown"]


class CompetitorKinds:
    ANIMAL: Final[CompetitorKind] = "animal"
    UNKNOWN: Final[CompetitorKind] = "unknown"


RequestMarket: TypeAlias = Literal["win", "place"]
MarketKey: TypeAlias = Literal["win", "place", "unknown"]


class MarketKeys:
    WIN: Final[RequestMarket] = "win"
    PLACE: Final[RequestMarket] = "place"
    UNKNOWN: Final[MarketKey] = "unknown"


MarketState: TypeAlias = Literal["unsettled", "settled", "void", "unknown"]


class MarketStates:
    UNSETTLED: Final[MarketState] = "unsettled"
    SETTLED: Final[MarketState] = "settled"
    VOID: Final[MarketState] = "void"
    UNKNOWN: Final[MarketState] = "unknown"


MarketPeriod: TypeAlias = Literal["full", "unknown"]


class MarketPeriods:
    FULL: Final[MarketPeriod] = "full"
    UNKNOWN: Final[MarketPeriod] = "unknown"


OutcomeKey: TypeAlias = Literal["entrant", "unknown"]


class OutcomeKeys:
    ENTRANT: Final[OutcomeKey] = "entrant"
    UNKNOWN: Final[OutcomeKey] = "unknown"


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


ExchangeOutcomeState: TypeAlias = Literal[
    "active", "removed", "winner", "loser", "closed", "unknown"
]


class ExchangeOutcomeStates:
    ACTIVE: Final[ExchangeOutcomeState] = "active"
    REMOVED: Final[ExchangeOutcomeState] = "removed"
    WINNER: Final[ExchangeOutcomeState] = "winner"
    LOSER: Final[ExchangeOutcomeState] = "loser"
    CLOSED: Final[ExchangeOutcomeState] = "closed"
    UNKNOWN: Final[ExchangeOutcomeState] = "unknown"


Surface: TypeAlias = Literal["turf", "all_weather", "dirt", "sand", "synthetic", "unknown"]


class Surfaces:
    TURF: Final[Surface] = "turf"
    ALL_WEATHER: Final[Surface] = "all_weather"
    DIRT: Final[Surface] = "dirt"
    SAND: Final[Surface] = "sand"
    SYNTHETIC: Final[Surface] = "synthetic"
    UNKNOWN: Final[Surface] = "unknown"


DividendPool: TypeAlias = Literal[
    "win", "place", "quinella", "exacta", "duet", "trifecta", "first4", "unknown"
]


class DividendPools:
    WIN: Final[DividendPool] = "win"
    PLACE: Final[DividendPool] = "place"
    QUINELLA: Final[DividendPool] = "quinella"
    EXACTA: Final[DividendPool] = "exacta"
    DUET: Final[DividendPool] = "duet"
    TRIFECTA: Final[DividendPool] = "trifecta"
    FIRST4: Final[DividendPool] = "first4"
    UNKNOWN: Final[DividendPool] = "unknown"


IncludeFlag: TypeAlias = Literal["coverage", "history", "racing"]


class IncludeFlags:
    COVERAGE: Final[IncludeFlag] = "coverage"
    HISTORY: Final[IncludeFlag] = "history"
    RACING: Final[IncludeFlag] = "racing"


SnapshotMode: TypeAlias = Literal["full", "none"]


class SnapshotModes:
    FULL: Final[SnapshotMode] = "full"
    NONE: Final[SnapshotMode] = "none"


class BudgetHeaders:
    """Response headers carrying the two budgets, as declared by the contract.

    Every `/v2` response declares all seven; `RETRY_AFTER` is additionally
    declared on 429 and 503. `MONTHLY_RESET` is an RFC 3339 instant — the rest
    are integers, and `RESET` is *seconds remaining*, not a timestamp.

    Names live here rather than inline so there is one place to reconcile with
    `openapi.json`, which `tests/test_contract_spec.py` does.
    """

    LIMIT: Final[str] = "X-RateLimit-Limit"
    REMAINING: Final[str] = "X-RateLimit-Remaining"
    RESET: Final[str] = "X-RateLimit-Reset"
    MONTHLY_LIMIT: Final[str] = "X-RateLimit-Monthly-Limit"
    MONTHLY_USED: Final[str] = "X-RateLimit-Monthly-Used"
    MONTHLY_REMAINING: Final[str] = "X-RateLimit-Monthly-Remaining"
    MONTHLY_RESET: Final[str] = "X-RateLimit-Monthly-Reset"
    RETRY_AFTER: Final[str] = "Retry-After"


class ErrorCodes:
    """Stable `code` members of an RFC 9457 problem document.

    Branch on these, never on `title` or `detail`. Unlike the other
    vocabularies here this one is deliberately not a Literal: the contract only
    grows, so `APIStatusError.code` stays `str` and an unrecognised code reaches
    you intact rather than failing to decode.
    """

    AUTHENTICATION_REQUIRED: Final[str] = "authentication_required"
    SCOPE_REQUIRED: Final[str] = "scope_required"
    PLAN_REQUIRED: Final[str] = "plan_required"
    ENTITLEMENT_EMPTY: Final[str] = "entitlement_empty"
    ACCOUNT_DISABLED: Final[str] = "account_disabled"
    RATE_LIMITED: Final[str] = "rate_limited"
    QUOTA_EXCEEDED: Final[str] = "quota_exceeded"
    QUOTA_UNAVAILABLE: Final[str] = "quota_unavailable"
    INVALID_REQUEST: Final[str] = "invalid_request"
    INVALID_FILTER: Final[str] = "invalid_filter"
    FILTER_REQUIRED: Final[str] = "filter_required"
    NOT_FOUND: Final[str] = "not_found"
    METHOD_NOT_ALLOWED: Final[str] = "method_not_allowed"
    UNSUPPORTED_MEDIA_TYPE: Final[str] = "unsupported_media_type"
    STREAM_UNAVAILABLE: Final[str] = "stream_unavailable"
    STREAM_LIMIT: Final[str] = "stream_limit"
    CURSOR_EXPIRED: Final[str] = "cursor_expired"
    CURSOR_SCOPE_CHANGED: Final[str] = "cursor_scope_changed"
    INTERNAL_ERROR: Final[str] = "internal_error"
    UNAVAILABLE: Final[str] = "unavailable"
