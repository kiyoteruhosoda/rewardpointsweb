"""Whether "has no local authentication" is expressed in the data (ADR-0034).

A user whose ``users.password_hash`` is NULL cannot sign in with a password, cannot change it,
and **cannot grow one through a reset either**. Only an explicit setting by an admin gives them one.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.domain.auth import master_data
from shared.infrastructure.models import PasswordResetToken, User

_SSO_ONLY = "ssoonly"


@pytest.fixture
def sso_only_user(engine: sa.Engine) -> int:
    """A user who can sign in only via SSO (has no password)."""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(
        username=_SSO_ONLY,
        email="sso-only@example.com",
        display_name="SSO だけ",
        password_hash=None,
    )
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def test_a_user_without_a_password_cannot_sign_in_with_one(client: TestClient, sso_only_user: int) -> None:
    response = client.post("/api/auth/login", json={"username": _SSO_ONLY, "password": "anything-at-all"})
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_credentials"


def test_a_reset_is_not_issued_for_a_user_without_a_password(
    client: TestClient, db_session: Session, sso_only_user: int
) -> None:
    """⚠ Without this, a single reset grows local authentication."""
    response = client.post("/api/auth/forgot-password", json={"username": _SSO_ONLY})
    # The response is the same as when there is no recipient (does not leak existence).
    assert response.status_code == 200
    assert db_session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == sso_only_user)) is None


def _take_the_password_away(db_session: Session, username: str) -> None:
    """Take away only the password of a signed-in user (the token stays as is)."""
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    user.password_hash = None
    db_session.commit()


def test_the_screen_is_told_whether_there_is_a_password(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """The screen looks at this to decide whether to show the path to change the password."""
    assert client.get("/api/auth/me", headers=admin_headers).json()["has_password"] is True

    _take_the_password_away(db_session, master_data.DEFAULT_ADMIN_USERNAME)
    assert client.get("/api/auth/me", headers=admin_headers).json()["has_password"] is False


def test_a_user_without_a_password_cannot_change_one(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """A user without a password cannot enter a "current password".

    The reason is not distinguished (so the presence of an entrance cannot be counted from outside).
    """
    _take_the_password_away(db_session, master_data.DEFAULT_ADMIN_USERNAME)

    response = client.post(
        "/api/auth/change-password",
        headers=admin_headers,
        json={"current_password": "", "new_password": "grown-out-of-nothing-1"},
    )
    assert response.status_code == 400


def test_an_administrator_can_give_a_password_on_purpose(
    client: TestClient, sso_only_user: int, admin_headers: dict[str, str]
) -> None:
    """Only an explicit operation gives someone a local account (ADR-0034)."""
    updated = client.put(
        f"/api/admin/users/{sso_only_user}",
        headers=admin_headers,
        json={"password": "given-on-purpose-1"},
    )
    assert updated.status_code == 200, updated.text
    signed_in = client.post("/api/auth/login", json={"username": _SSO_ONLY, "password": "given-on-purpose-1"})
    assert signed_in.status_code == 200, signed_in.text
