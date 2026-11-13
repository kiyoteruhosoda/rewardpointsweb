"""Input validation failures (422) are returned in a form the screen can read.

FastAPI's default ``{"detail": [...]}`` is an array, which the SPA's ``extractErrorCode``
(``frontend/src/services/api.ts``) cannot match. Whatever field is wrong, it only becomes
the ``unknown_error`` message and the user has no way to fix it. On top of that, the default
body carries the submitted value as ``input`` as is (including a typed
password). This pins the shape, the code and **that values do not appear**.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from presentation.fastapi.error_handling import VALIDATION_ERROR_CODE

# Rejected for being under 8 characters. With the default response this value would come back in ``input``.
_PASSWORD = "secret"


def test_validation_failure_uses_the_same_error_shape_as_other_failures(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "display_name": "こども", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["password"]}}


def test_the_response_never_echoes_what_was_sent(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Return only the field names. If ``input`` were included, passwords and email addresses would leak."""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "email": "kid@invalid", "display_name": "こども", "password": _PASSWORD},
    )

    assert response.status_code == 422
    body = response.text
    assert _PASSWORD not in body
    assert "kid@invalid" not in body
    assert response.json()["detail"]["fields"] == ["email", "password"]


def test_missing_body_is_reported_without_a_field_name(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Return the same shape when there is no body at all (the field name is ``body``)."""
    response = client.post("/api/admin/users", headers=admin_headers)

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["body"]}}


def test_account_signup_reports_the_field_that_failed(client: TestClient) -> None:
    """Account creation with an invitation code (unauthenticated) returns the same shape."""
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": "ABCDE12345", "username": "kid", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["password"]}}
