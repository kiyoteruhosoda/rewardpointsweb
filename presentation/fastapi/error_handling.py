"""Recording failed responses, and mapping unexpected exceptions to HTTP responses (the last resort).

**Failures turn into responses outside the router.** ``HTTPException``, input validation errors
and domain exceptions all leave the router the moment they are raised, and an exception handler
builds the response. So adding a ``logger`` to a router does not record the failure, and the app
log keeps only the single access-log line (just the status code). "What happened" — the error
code, the fields that failed validation, the traceback — is known only in the handlers.

So failure recording is gathered here. No per-router ``try/except`` is needed, and the
granularity of recording is decided in one place. The log level is decided from the status code
by :func:`log_level_for_status` (the access log uses the same function).

For unexpected exceptions, the response is also built here. Without a catch-all, Starlette
returns a **text/plain** body ``Internal Server Error``. The API client (SPA) reads the body as
JSON, so on receiving it, it cannot extract an error code and can only show the generic
``unknown_error`` text (and the cause cannot be narrowed down). So we

- normalise it to the JSON ``{"detail": {"error": "internal_error"}}`` (the display text is
  decided by the frontend; the i18n section of CLAUDE.md)
- log it with the traceback (stored in the ``trace`` column of the ``log`` table)

Mapping of domain exceptions is handled by each context's ``error_handling``, so do not add
individual exceptions here (use :func:`log_failed_request` for recording).

The response for input validation failures (422) is also built here. FastAPI's default is an
**array**, ``{"detail": [{"type": ..., "loc": ..., "input": ...}]}``, which means

- the UI cannot show the cause. The SPA extracts the code from ``{"detail": {"error": "..."}}``
  (``frontend/src/services/api.ts``). An array does not fit, so whatever is wrong with the
  input, the text is always the generic ``unknown_error``.
- the submitted values are echoed back. ``input`` holds the failed field's value — a too-short
  password or an email address — in plain text. The log is narrowed to field names and reasons
  (:func:`_validation_failures`), yet the response would send them out.

So it is normalised to the same shape as other failures, carrying **field names only**
(``fields``). Neither values nor Pydantic's internal reasons (``string_too_short`` etc.) go into
the response.

The catch-all is placed **twice**.

1. :class:`~presentation.fastapi.middleware.internal_error.InternalErrorMiddleware`
   (the normal path). It sits **inside** CORS and request logging, so the response carries CORS
   headers and ``X-Request-Id``, and the access log records it as a 500.
2. The ``Exception`` handler (a safety net). It only works when a middleware outside 1 itself
   fails. Starlette mounts this handler on ``ServerErrorMiddleware`` (outside all middleware),
   so responses returned from it carry no CORS headers. That is why the normal path is left
   to 1.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from shared.kernel.logging.request_context import current_request_id

logger = logging.getLogger(__name__)

INTERNAL_ERROR_CODE = "internal_error"
VALIDATION_ERROR_CODE = "validation_error"

# Location in the request at the head of ``loc``. Stripped when building field names.
_LOCATIONS = frozenset({"body", "query", "path", "header", "cookie"})

# 401 happens routinely (expired tokens, API calls while not logged in).
# Only this one is lowered to INFO. The other 4xx are raised to WARNING as "a mistake by the
# user or caller", so they are not buried when filtering the log.
_ROUTINE_STATUS_CODES = frozenset({status.HTTP_401_UNAUTHORIZED})

# Input validation failure (the status FastAPI returns). ``status``'s
# ``HTTP_422_UNPROCESSABLE_ENTITY`` is deprecated in Starlette and merely referencing it
# emits a warning, so the number is kept here.
_VALIDATION_ERROR_STATUS = 422


def log_level_for_status(status_code: int) -> int:
    """Decide the log level from an HTTP status code.

    The access log (``RequestLoggingMiddleware``) and failure recording (this module) share the
    same policy, so the decision lives only here.
    """
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return logging.ERROR
    if status_code >= status.HTTP_400_BAD_REQUEST and status_code not in _ROUTINE_STATUS_CODES:
        return logging.WARNING
    return logging.INFO


def error_code_of(detail: object) -> str | None:
    """Extract only the error code from the response body (``detail``).

    This app's responses are uniformly ``{"error": "..."}``. Strings such as FastAPI's default
    ``"Not Found"`` are taken as is. **Nothing but the code is extracted** — ``detail`` may
    contain the name of the target, and moving values into the log would make it PII.
    """
    if isinstance(detail, dict):
        code = detail.get("error")
        return str(code) if code is not None else None
    if isinstance(detail, str):
        return detail
    return None


def log_failed_request(request: Request, status_code: int, error_code: str | None) -> None:
    """Record that an error response is being returned. Also called from domain exception handlers.

    The error code **goes into the message**. Only the items that have columns
    (``message`` / ``path`` / ``method`` / ``status_code`` / ``trace``) are kept in the ``log``
    table; the rest of ``extra`` appears only in the JSON on stdout. The message carries it too,
    so "which code it failed with" can be read from the admin UI.
    """
    logger.log(
        log_level_for_status(status_code),
        "request_failed: %s",
        error_code or "unknown",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "error_code": error_code,
        },
    )


def log_unhandled_exception(request: Request, error: Exception) -> None:
    """Record an unexpected exception with its traceback (stored in the ``trace`` column of ``log``)."""
    logger.exception(
        "unhandled_exception",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
        exc_info=error,
    )


def internal_error_response(request: Request, error: Exception) -> JSONResponse:
    """Record the exception and build a 500 response carrying only the error code.

    The exception's contents are not put in the response (to avoid exposing internals). Tracing
    is done via ``requestId``.
    """
    log_unhandled_exception(request, error)
    request_id = current_request_id()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": {"error": INTERNAL_ERROR_CODE}},
        headers={"X-Request-Id": request_id} if request_id else None,
    )


def _validation_failures(error: RequestValidationError) -> str:
    """List the fields that failed validation in the form ``body.email:missing``.

    **Input values themselves are excluded** (including ``ctx`` or ``input`` would move email
    addresses and passwords into the log; the logging section of CLAUDE.md). Field names and failure
    reasons alone are enough to trace which request was wrong and how.
    """
    return ",".join(
        "{}:{}".format(
            ".".join(str(part) for part in item.get("loc", ())),
            item.get("type", "invalid"),
        )
        for item in error.errors()
    )


def _field_name(location: tuple[object, ...]) -> str:
    """``("body", "display_name")`` → ``"display_name"``.

    Drop the leading request location and join the rest with ``.``. Array indices are not field
    names, so they are dropped (``("body", 0, "name")`` → ``"name"``). When the body itself could
    not be read nothing remains, so the location itself becomes the name.
    """
    parts = [str(part) for part in location if not isinstance(part, int)]
    if parts and parts[0] in _LOCATIONS:
        head, *rest = parts
        return ".".join(rest) if rest else head
    return ".".join(parts) or "body"


def invalid_field_names(error: RequestValidationError) -> list[str]:
    """List the names of fields that failed validation, deduplicated, in order of appearance.

    **Returns names only**. Neither values (``input``) nor Pydantic's reasons (``type``) go into
    the response — values contain typed passwords and email addresses.
    """
    names: list[str] = []
    for item in error.errors():
        name = _field_name(tuple(item.get("loc", ())))
        if name not in names:
            names.append(name)
    return names


def validation_error_response(error: RequestValidationError) -> JSONResponse:
    """Return an input validation failure in the same ``{"error": ...}`` shape as other failures."""
    return JSONResponse(
        status_code=_VALIDATION_ERROR_STATUS,
        content={"detail": {"error": VALIDATION_ERROR_CODE, "fields": invalid_field_names(error)}},
    )


def register_error_handling(app: FastAPI) -> None:
    """Register failure recording and the safety net for exceptions raised outside the middleware."""

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, error: StarletteHTTPException) -> Response:
        log_failed_request(request, error.status_code, error_code_of(error.detail))
        return await http_exception_handler(request, error)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, error: RequestValidationError) -> Response:
        invalid_fields = _validation_failures(error)
        logger.warning(
            "request_validation_failed: %s",
            invalid_fields,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": _VALIDATION_ERROR_STATUS,
                "invalid_fields": invalid_fields,
            },
        )
        return validation_error_response(error)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        return internal_error_response(request, error)


__all__ = [
    "INTERNAL_ERROR_CODE",
    "VALIDATION_ERROR_CODE",
    "error_code_of",
    "internal_error_response",
    "invalid_field_names",
    "log_failed_request",
    "log_level_for_status",
    "log_unhandled_exception",
    "register_error_handling",
    "validation_error_response",
]
