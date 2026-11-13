"""Propagation of request context (``requestId`` etc.).

Holds values set by the middleware in ``contextvars`` and attaches them to every
log record automatically (``logging_config.RequestContextFilter``).
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_hash_var: ContextVar[str | None] = ContextVar("user_id_hash", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def current_user_id_hash() -> str | None:
    return user_id_hash_var.get()


__all__ = [
    "current_request_id",
    "current_user_id_hash",
    "request_id_var",
    "user_id_hash_var",
]
