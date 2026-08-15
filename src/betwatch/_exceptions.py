from __future__ import annotations

from typing import Any


class BetwatchError(Exception):
    """Base error for the public Betwatch SDK."""


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


class APIDecodeError(BetwatchError):
    """The HTTP body was not the expected public schema."""

    def __init__(self, path: str, exc: Exception) -> None:
        self.path = path
        super().__init__(f"{path}: could not decode response: {exc}")


class APIStatusError(BetwatchError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        path: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.path = path
        self.code: str | None = None
        self.detail: str | None = None
        self.title: str | None = None
        self.request_id = request_id
        self.trace_id = trace_id
        if isinstance(body, dict):
            code = body.get("code")
            detail = body.get("detail")
            title = body.get("title")
            self.code = code if isinstance(code, str) else None
            self.detail = detail if isinstance(detail, str) else None
            self.title = title if isinstance(title, str) else None
            if self.request_id is None:
                rid = body.get("requestId")
                self.request_id = rid if isinstance(rid, str) else None
            if self.trace_id is None:
                tid = body.get("traceId")
                self.trace_id = tid if isinstance(tid, str) else None

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.detail and self.detail not in parts[0]:
            parts.append(self.detail)
        if self.code:
            parts.append(f"code={self.code}")
        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")
        return " — ".join(parts)


class BadRequestError(APIStatusError):
    """HTTP 400. Check filter values and datetime formats."""


class AuthenticationError(APIStatusError):
    """HTTP 401. The API key is missing, disabled, or not sent as X-API-Key."""


class PermissionDeniedError(APIStatusError):
    """HTTP 403. The key lacks the required scope (rest or stream)."""


class NotFoundError(APIStatusError):
    """HTTP 404. The public id does not exist (or is not visible to this key)."""


class UnprocessableEntityError(APIStatusError):
    """HTTP 422. A required filter is missing or a value is malformed."""


class RateLimitError(APIStatusError):
    """HTTP 429. Monthly quota or stream lease is exhausted. Back off and retry."""


class InternalServerError(APIStatusError):
    """HTTP 5xx."""


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


_STATUS_ERRORS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def error_for_status(
    status_code: int,
    *,
    path: str,
    body: Any = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> APIStatusError:
    cls = _STATUS_ERRORS.get(status_code)
    if cls is None and status_code >= 500:
        cls = InternalServerError
    if cls is None:
        cls = APIStatusError
    detail = ""
    if isinstance(body, dict) and isinstance(body.get("detail"), str):
        detail = f": {body['detail']}"
    return cls(
        f"{path} failed: {status_code}{detail}",
        status_code=status_code,
        body=body,
        path=path,
        request_id=request_id,
        trace_id=trace_id,
    )
