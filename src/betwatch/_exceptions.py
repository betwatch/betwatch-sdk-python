from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._ratelimit import RateLimit
from .types.enums import ErrorCodes


class BetwatchError(Exception):
    """Base error for the public Betwatch SDK."""


@dataclass(frozen=True, slots=True)
class FieldError:
    """One entry of a problem document's `errors[]`.

    `value` is whatever the server echoed back, so it stays untyped.
    """

    message: str
    location: str | None = None
    value: Any = None

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


class APIKeyNotSetError(BetwatchError):
    def __init__(self) -> None:
        super().__init__(
            "Set BETWATCH_API_KEY or pass api_key= to Betwatch(). "
            "Contact api@betwatch.com if you do not have a key."
        )


class FilterRequiredError(BetwatchError, ValueError):
    """A list route was called without a required narrowing filter.

    Raised locally before any HTTP request so agents fail fast.
    """

    def __init__(self, resource: str, required: str, example: str) -> None:
        self.resource = resource
        self.required = required
        super().__init__(f"{resource}.list() requires {required}. Example: {example}")


class CredentialInQueryError(BetwatchError, ValueError):
    """A query parameter looked like a credential.

    The API refuses any request carrying `apikey`, `api_key`, `key`, `token`,
    or `access_token` in the query with 401 — even when `X-API-Key` is also
    present — so a URL is never a place to put a key. Raised locally, before
    any request, so the SDK cannot build one.
    """

    def __init__(self, params: list[str]) -> None:
        self.params = params
        super().__init__(
            f"refusing to send {', '.join(params)} as a query parameter: "
            "the Betwatch API takes credentials only in the X-API-Key header. "
            "Pass the key as Betwatch(api_key=...) or set BETWATCH_API_KEY."
        )


class BootstrapFailedError(BetwatchError):
    """A `snapshot=full` stream lost its connection too many times to finish.

    There is no resumable position before `sync`, so every drop restarts the
    whole snapshot. When the snapshot takes longer to build than the connection
    survives, retrying cannot converge — so the SDK stops rather than looping.

    `snapshot="full"` is only accepted for an event, meeting, or venue now, so
    a bootstrap this fragile means a single race is taking too long or the
    connection is unhealthy. Bootstrap over REST instead, which is resumable:
    `client.follow(client.snapshot(RacingScope(event=...)))`.
    """

    def __init__(self, restarts: int, scope: object = None) -> None:
        self.restarts = restarts
        super().__init__(
            f"the stream snapshot restarted {restarts} times without completing. "
            "Bootstrap over REST instead, which is resumable: "
            "client.follow(client.snapshot(RacingScope(sport=..., country=...)))"
        )


class UnexpectedRedirectError(BetwatchError):
    """Something answered with a redirect. `/v2` never does.

    Betwatch resolves a merged id server-side and returns the surviving resource
    as 200, so a 3xx did not come from the API — it came from something between
    you and it: an ingress, a proxy, a captive portal, a misconfigured CDN.
    That is what this error is for, and why it names the location.

    Raised rather than followed. Following would send `X-API-Key` to whatever
    host `Location` names — httpx strips `Authorization` across origins but not
    custom headers — and a credential is not something to forward on the say-so
    of a hop you did not expect to be there.
    """

    def __init__(self, path: str, status_code: int, location: str | None) -> None:
        self.path = path
        self.status_code = status_code
        self.location = location
        super().__init__(
            f"{path}: unexpected {status_code} redirect to {location or 'an unstated location'}. "
            "The /v2 contract declares no 3xx responses, so the SDK does not follow one."
        )


class APIDecodeError(BetwatchError):
    """The HTTP body was not the expected public schema."""

    def __init__(self, path: str, exc: Exception) -> None:
        self.path = path
        super().__init__(f"{path}: could not decode response: {exc}")


class APIConnectionError(BetwatchError):
    """The API could not be reached after the configured retry budget."""

    def __init__(self, path: str, exc: Exception) -> None:
        self.path = path
        super().__init__(f"{path}: connection failed: {exc}")


class APITimeoutError(APIConnectionError):
    """The API request timed out after the configured retry budget."""


class StreamDecodeError(BetwatchError):
    """A named stream frame violated the public SSE contract."""

    def __init__(self, event: str | None, cursor: str | None, exc: Exception | str) -> None:
        self.event = event
        self.cursor = cursor
        self.detail = str(exc)
        super().__init__(
            f"/v2/stream: invalid {event or 'unnamed'} frame at {cursor or 'no cursor'}: {exc}"
        )


def _str_member(body: Any, name: str) -> str | None:
    if isinstance(body, dict):
        value = body.get(name)
        if isinstance(value, str):
            return value
    return None


def _field_errors(body: Any) -> list[FieldError]:
    if not isinstance(body, dict):
        return []
    raw = body.get("errors")
    if not isinstance(raw, list):
        return []
    errors: list[FieldError] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, str):
            continue
        location = item.get("location")
        errors.append(
            FieldError(
                message=message,
                location=location if isinstance(location, str) else None,
                value=item.get("value"),
            )
        )
    return errors


# Rendered in place of a request id that the contract guarantees but this
# response did not carry — a proxy 502, or a body that never reached the API.
# Showing the absence beats hiding it: it says where to look.
NO_REQUEST_ID = "<none>"


class APIStatusError(BetwatchError):
    """An RFC 9457 problem document returned by the API.

    Branch on `code` (see `ErrorCodes`), never on `title` or `detail`.
    Quote `request_id` and `trace_id` when contacting support.

    `request_id` is required by the contract — the request-id middleware runs
    before anything that can fail — so it is rendered unconditionally and is
    absent only when the failure never reached the API. `trace_id` is optional:
    it depends on the request having been traced.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        path: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        retry_after: float | None = None,
        rate_limit: RateLimit | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.path = path
        self.retry_after = retry_after
        self.rate_limit = rate_limit
        self.code = _str_member(body, "code")
        self.detail = _str_member(body, "detail")
        self.title = _str_member(body, "title")
        self.type = _str_member(body, "type")
        self.instance = _str_member(body, "instance")
        self.errors = _field_errors(body)
        # The body is authoritative: the contract requires requestId there,
        # while the header can be stripped by an intermediary.
        self.request_id = _str_member(body, "requestId") or request_id
        self.trace_id = trace_id or _str_member(body, "traceId")

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.detail and self.detail not in parts[0]:
            parts.append(self.detail)
        if self.errors:
            parts.append("; ".join(str(err) for err in self.errors))
        if self.code:
            parts.append(f"code={self.code}")
        parts.append(f"request_id={self.request_id or NO_REQUEST_ID}")
        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")
        return " — ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status_code={self.status_code}, code={self.code!r}, "
            f"request_id={self.request_id!r}, trace_id={self.trace_id!r})"
        )


class BadRequestError(APIStatusError):
    """HTTP 400. Check filter values and datetime formats."""


class AuthenticationError(APIStatusError):
    """HTTP 401. The API key is missing, disabled, or not sent as X-API-Key."""


class PermissionDeniedError(APIStatusError):
    """HTTP 403. This key is not permitted to make the request.

    `scope_required` means the key lacks the rest or stream scope;
    `plan_required` means the product does not include the surface.
    """


class EntitlementEmptyError(PermissionDeniedError):
    """HTTP 403 `entitlement_empty`. The key's product grants no sports or countries.

    This is a provisioning problem, not an empty raceday. Contact
    api@betwatch.com — retrying will not change the answer.
    """


class AccountDisabledError(PermissionDeniedError):
    """HTTP 403 `account_disabled`. The account has been disabled by an operator."""


class NotFoundError(APIStatusError):
    """HTTP 404. The public id does not exist (or is not visible to this key)."""


class UnprocessableEntityError(APIStatusError):
    """HTTP 422. A required filter is missing or a value is malformed."""


class CursorError(APIStatusError):
    """HTTP 409 `cursor_expired` / `cursor_scope_changed`. The cursor is dead.

    `cursor_expired` means it is older than the plan's replay window;
    `cursor_scope_changed` means it was minted for different filters, a
    different entitlement, or a different account. Neither is fixed by
    retrying: bootstrap again over REST and reconnect with the fresh cursor.

    On a stream this is intercepted and re-raised as `ResyncRequired`, which
    carries this as its cause.
    """


class MethodNotAllowedError(APIStatusError):
    """HTTP 405. The public API is read-only; every operation is a GET."""


class UnsupportedMediaTypeError(APIStatusError):
    """HTTP 406/415. Ask for `application/json`."""


class RateLimitError(APIStatusError):
    """HTTP 429 `rate_limited`. The short per-minute window is exhausted.

    Worth retrying: wait `retry_after` seconds, which the server always sends.
    The SDK already does this within its retry budget.
    """


class QuotaExceededError(APIStatusError):
    """HTTP 429 `quota_exceeded`. The monthly quota is spent.

    Deliberately *not* a subclass of `RateLimitError`: it resets at
    `rate_limit.monthly_reset`, possibly weeks away, so sleeping on it burns a
    retry budget for nothing. Alert and upgrade the plan instead.
    """


class StreamLimitError(APIStatusError):
    """HTTP 429 `stream_limit`. The plan's concurrent-stream cap is reached.

    Also not a `RateLimitError`: waiting does not help, closing a connection
    does. One filtered stream can cover many races — a connection per race is
    the pattern this is telling you to stop.
    """


class InternalServerError(APIStatusError):
    """HTTP 5xx. Retry with backoff; quote `request_id` if it persists."""


class ServiceUnavailableError(InternalServerError):
    """HTTP 503 `unavailable` / `quota_unavailable` / `stream_unavailable`.

    A dependency is briefly unavailable, or the quota counter could not be
    read and the request was refused rather than served unmetered. Retryable
    with backoff.
    """


class ResyncRequired(BetwatchError):
    """The retained stream hit a recovery boundary.

    Do not reconnect with the old cursor. Take a new snapshot, then
    `client.follow(snapshot)`.
    """

    def __init__(self, cursor: str | None, reason: str | None = None) -> None:
        self.cursor = cursor
        self.reason = reason
        hint = "Re-snapshot the event, then follow the new cursor."
        if reason:
            super().__init__(f"stream resync required ({reason}). {hint}")
        else:
            super().__init__(f"stream resync required. {hint}")


# An unrecognised code falls back to its HTTP class, so a code added after
# this release still raises something a caller can handle.
_STATUS_ERRORS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: CursorError,
    405: MethodNotAllowedError,
    406: UnsupportedMediaTypeError,
    415: UnsupportedMediaTypeError,
    422: UnprocessableEntityError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}

# Codes whose meaning is narrower than their status. Three codes share 429 and
# only one of them is worth waiting out; three share 403 and they need
# different operator action. The status alone cannot tell them apart.
_CODE_ERRORS: dict[str, type[APIStatusError]] = {
    ErrorCodes.QUOTA_EXCEEDED: QuotaExceededError,
    ErrorCodes.STREAM_LIMIT: StreamLimitError,
    ErrorCodes.ENTITLEMENT_EMPTY: EntitlementEmptyError,
    ErrorCodes.ACCOUNT_DISABLED: AccountDisabledError,
    ErrorCodes.CURSOR_EXPIRED: CursorError,
    ErrorCodes.CURSOR_SCOPE_CHANGED: CursorError,
    ErrorCodes.QUOTA_UNAVAILABLE: ServiceUnavailableError,
    ErrorCodes.STREAM_UNAVAILABLE: ServiceUnavailableError,
    ErrorCodes.UNAVAILABLE: ServiceUnavailableError,
    ErrorCodes.INTERNAL_ERROR: InternalServerError,
}

# The retry table from the published error reference, keyed on code because
# the status cannot express it: 429 is both "slow down" and "you are out until
# next month", and 503 is always worth another attempt.
_RETRYABLE_CODES = frozenset(
    {
        ErrorCodes.RATE_LIMITED,
        ErrorCodes.QUOTA_UNAVAILABLE,
        ErrorCodes.STREAM_UNAVAILABLE,
        ErrorCodes.UNAVAILABLE,
        ErrorCodes.INTERNAL_ERROR,
    }
)

# Retrying these unchanged cannot help. Everything else non-retryable is a
# request the caller has to fix, or a credential/entitlement problem.
_TERMINAL_CODES = frozenset(
    {
        ErrorCodes.QUOTA_EXCEEDED,
        ErrorCodes.STREAM_LIMIT,
        ErrorCodes.AUTHENTICATION_REQUIRED,
        ErrorCodes.SCOPE_REQUIRED,
        ErrorCodes.PLAN_REQUIRED,
        ErrorCodes.ENTITLEMENT_EMPTY,
        ErrorCodes.ACCOUNT_DISABLED,
        ErrorCodes.INVALID_REQUEST,
        ErrorCodes.INVALID_FILTER,
        ErrorCodes.FILTER_REQUIRED,
        ErrorCodes.NOT_FOUND,
        ErrorCodes.METHOD_NOT_ALLOWED,
        ErrorCodes.UNSUPPORTED_MEDIA_TYPE,
        # Not "as-is": these mean re-bootstrap over REST and reconnect, which
        # the stream does rather than repeating the same request.
        ErrorCodes.CURSOR_EXPIRED,
        ErrorCodes.CURSOR_SCOPE_CHANGED,
    }
)


def is_retryable_code(code: str | None) -> bool | None:
    """True to retry, False to fail fast, None when the code says nothing."""
    if code is None:
        return None
    if code in _RETRYABLE_CODES:
        return True
    if code in _TERMINAL_CODES:
        return False
    return None


def error_class_for(status_code: int, code: str | None) -> type[APIStatusError]:
    if code is not None:
        by_code = _CODE_ERRORS.get(code)
        if by_code is not None:
            return by_code
    cls = _STATUS_ERRORS.get(status_code)
    if cls is None and status_code >= 500:
        cls = InternalServerError
    return cls or APIStatusError


def error_for_status(
    status_code: int,
    *,
    path: str,
    body: Any = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    retry_after: float | None = None,
    rate_limit: RateLimit | None = None,
) -> APIStatusError:
    code = _str_member(body, "code")
    detail = _str_member(body, "detail")
    return error_class_for(status_code, code)(
        f"{path} failed: {status_code}" + (f": {detail}" if detail else ""),
        status_code=status_code,
        body=body,
        path=path,
        request_id=request_id,
        trace_id=trace_id,
        retry_after=retry_after,
        rate_limit=rate_limit,
    )
