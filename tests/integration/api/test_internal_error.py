"""Verifies that an unexpected exception comes back as an error code the frontend can read.

Without a handler, Starlette returns a text/plain ``Internal Server Error``.
The API client reads the body as JSON, so in that case it cannot extract a code and
can only show ``unknown_error`` (and the cause cannot be narrowed down either).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated

import pytest
import sqlalchemy as sa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from presentation.fastapi.dependencies.auth import get_current_principal
from presentation.fastapi.error_handling import INTERNAL_ERROR_CODE
from shared.application.authenticated_principal import AuthenticatedPrincipal

_ALLOWED_ORIGIN = "https://app.example.com"


def _add_failing_endpoint(app: FastAPI) -> None:
    @app.get("/api/test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    @app.get("/api/test/authenticated-boom")
    async def _authenticated_boom(
        _principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    ) -> None:
        raise RuntimeError("boom")


@pytest.fixture
def client_with_failing_endpoint(app: FastAPI) -> TestClient:
    _add_failing_endpoint(app)
    # Check the response without raising the exception (same as the production ASGI server).
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def cors_client_with_failing_endpoint(
    engine: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Build the app with a configuration that allows a cross-origin frontend."""
    from presentation.fastapi.app import create_app

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", f'["{_ALLOWED_ORIGIN}"]')
    app = create_app()
    _add_failing_endpoint(app)
    yield TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_a_json_error_code(client_with_failing_endpoint: TestClient) -> None:
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]["error"] == INTERNAL_ERROR_CODE


def test_unhandled_exception_does_not_leak_the_exception_text(client_with_failing_endpoint: TestClient) -> None:
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert "boom" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_exception_carries_the_request_id(client_with_failing_endpoint: TestClient) -> None:
    """Put the requestId in the response too, so the matching log line can be looked up."""
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert response.headers.get("X-Request-Id")


def test_cross_origin_client_can_read_the_error_code(cors_client_with_failing_endpoint: TestClient) -> None:
    """Add CORS headers to the 500 response too, so the body can be read cross-origin.

    The ``Exception`` handler sits outside the CORS middleware, so relying on it alone means
    ``Access-Control-Allow-Origin`` is missing. The browser drops the body and the screen falls
    back to ``unknown_error`` (defeating the point of adding the catch-all).
    """
    response = cors_client_with_failing_endpoint.get("/api/test/boom", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == INTERNAL_ERROR_CODE
    assert response.headers.get("access-control-allow-origin") == _ALLOWED_ORIGIN


def test_failed_request_is_recorded_in_the_access_log(
    client_with_failing_endpoint: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """500s go into the access log too. If the exception slips past the logging layer, only 500s go missing."""
    with caplog.at_level(logging.INFO, logger="app.request"):
        client_with_failing_endpoint.get("/api/test/boom")

    statuses = [getattr(record, "status_code", None) for record in caplog.records if record.name == "app.request"]
    assert 500 in statuses


_ERROR_LOGGER = "presentation.fastapi.error_handling"


def _error_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == _ERROR_LOGGER]


def test_unhandled_exception_is_logged_with_a_traceback(
    client_with_failing_endpoint: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the traceback lets us trace the cause. It goes into the ``trace`` column of the ``log`` table."""
    with caplog.at_level(logging.DEBUG, logger=_ERROR_LOGGER):
        client_with_failing_endpoint.get("/api/test/boom")

    records = _error_records(caplog)
    assert [record.levelno for record in records] == [logging.ERROR]
    assert records[0].message == "unhandled_exception"
    assert records[0].exc_info is not None


def test_client_error_is_logged_with_its_error_code(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """An ``HTTPException`` such as 404 also records "what happened".

    The error code is also put in the message. Only the column fields go into the ``log`` table,
    and the rest of ``extra`` only appears in the stdout JSON.
    """
    with caplog.at_level(logging.DEBUG, logger=_ERROR_LOGGER):
        assert client.delete("/api/admin/users/999999", headers=admin_headers).status_code == 404

    records = _error_records(caplog)
    assert [record.levelno for record in records] == [logging.WARNING]
    assert records[0].getMessage() == "request_failed: user_not_found"
    assert records[0].status_code == 404  # type: ignore[attr-defined]


def test_domain_error_is_logged(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """Domain exception handlers record through the same catch-all (level and fields match).

    admin has no family scope (ADR-0018), so a family party (member) is used to
    reach the domain exception.
    """
    password = "dad-pass-123"
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "dad", "display_name": "dad", "password": password, "roles": ["member"]},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/auth/login", json={"username": "dad", "password": password})
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    with caplog.at_level(logging.DEBUG, logger=_ERROR_LOGGER):
        assert client.get("/api/families/999999", headers=member_headers).status_code == 403

    records = _error_records(caplog)
    assert [record.error_code for record in records] == ["family_access_denied"]  # type: ignore[attr-defined]


def test_validation_failure_logs_the_fields_but_not_the_values(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Keep only the field name and reason. Logging the input would move PII into logs (CLAUDE.md "Logging")."""
    with caplog.at_level(logging.DEBUG, logger=_ERROR_LOGGER):
        response = client.post("/api/auth/login", json={"username": "leaked-user"})

    assert response.status_code == 422
    records = _error_records(caplog)
    assert [record.levelno for record in records] == [logging.WARNING]
    assert "body.password:missing" in records[0].invalid_fields  # type: ignore[attr-defined]
    assert "leaked-user" not in records[0].getMessage()


def test_the_500_log_line_knows_whose_request_it_was(
    client_with_failing_endpoint: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """When an authenticated request fails, the log line carries ``user_id_hash``.

    If ``InternalErrorMiddleware`` were written with ``BaseHTTPMiddleware``, downstream would run in a
    **separate task**, so the ``contextvars`` set by the auth dependency would not propagate and
    only the 500 line would lack "whose request it was". That is why it is written as plain ASGI.
    """
    with caplog.at_level(logging.DEBUG, logger=_ERROR_LOGGER):
        response = client_with_failing_endpoint.get("/api/test/authenticated-boom", headers=admin_headers)

    assert response.status_code == 500
    records = _error_records(caplog)
    assert [record.user_id_hash for record in records] != [None]  # type: ignore[attr-defined]


def _access_log_lines(caplog: pytest.LogCaptureFixture, path: str) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "app.request" and record.path == path  # type: ignore[attr-defined]
    ]


def test_the_access_log_line_knows_whose_request_it_was(
    client_with_failing_endpoint: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """For an authenticated request, the ``http_request`` line carries ``user_id_hash``.

    With ``BaseHTTPMiddleware``, ``RequestLoggingMiddleware`` would leave it empty, for the same reason as the 500 line.
    Also checks the line has the same user and the value does not leak into the next unauthenticated request.
    """
    with caplog.at_level(logging.DEBUG):
        response = client_with_failing_endpoint.get("/api/test/authenticated-boom", headers=admin_headers)
        client_with_failing_endpoint.get("/api/test/authenticated-boom")
        client_with_failing_endpoint.get("/api/test/boom")

    signed_in, signed_out = _access_log_lines(caplog, "/api/test/authenticated-boom")
    assert response.status_code == 500
    assert signed_in.status_code == 500  # type: ignore[attr-defined]
    assert signed_in.user_id_hash is not None  # type: ignore[attr-defined]
    assert signed_in.request_id == response.headers["X-Request-Id"]  # type: ignore[attr-defined]
    assert signed_out.status_code == 401  # type: ignore[attr-defined]
    assert signed_out.user_id_hash is None  # type: ignore[attr-defined]
    assert [line.user_id_hash for line in _access_log_lines(caplog, "/api/test/boom")] == [None]  # type: ignore[attr-defined]
