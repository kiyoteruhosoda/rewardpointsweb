import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.email_sender.domain.email_message import EmailMessage
from bounded_contexts.email_sender.infrastructure.smtp_email_sender import SmtpEmailSender
from shared.domain.auth import master_data
from shared.infrastructure.models import PasswordResetToken, User


def test_login_success(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": master_data.DEFAULT_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_credentials"


def test_login_with_an_expired_temporary_password_says_so(client: TestClient, db_session: Session) -> None:
    """An expired temporary password is rejected, but the reason is given (ADR-0011).

    It used to be collapsed into ``invalid_credentials``, so the user only saw "something that should be right
    does not work" and could not tell that they should ask a parent to reissue it.
    """
    from datetime import timedelta

    from werkzeug.security import generate_password_hash

    from shared.kernel.timestamps import utcnow

    db_session.add(
        User(
            username="kid",
            email=None,
            display_name="こども",
            password_hash=generate_password_hash("temp-pass-1"),
            is_active=True,
            must_change_password=True,
            temporary_password_expires_at=utcnow() - timedelta(hours=1),
        )
    )
    db_session.commit()

    expired = client.post("/api/auth/login", json={"username": "kid", "password": "temp-pass-1"})
    assert expired.status_code == 401
    assert expired.json()["detail"]["error"] == "temporary_password_expired"

    # Someone who does not know the value learns nothing, as before
    wrong = client.post("/api/auth/login", json={"username": "kid", "password": "not-the-password"})
    assert wrong.json()["detail"]["error"] == "invalid_credentials"


def test_me_requires_authentication(client: TestClient) -> None:
    client.cookies.clear()
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_scopes(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == master_data.DEFAULT_ADMIN_USERNAME
    assert data["email"] == "admin@example.com"
    assert data["display_name"] == master_data.DEFAULT_ADMIN_DISPLAY_NAME
    assert data["must_change_password"] is False
    assert "user:manage" in data["scopes"]


def test_refresh_issues_new_pair(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": master_data.DEFAULT_ADMIN_PASSWORD},
    ).json()
    response = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rejects_access_token(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": master_data.DEFAULT_ADMIN_PASSWORD},
    ).json()
    response = client.post("/api/auth/refresh", json={"refresh_token": login["access_token"]})
    assert response.status_code == 401


def test_change_password_roundtrip(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/auth/change-password",
        headers=admin_headers,
        json={"current_password": master_data.DEFAULT_ADMIN_PASSWORD, "new_password": "new-password-1"},
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin@example.com", "password": "new-password-1"},
        ).status_code
        == 200
    )


def test_change_password_wrong_current(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/auth/change-password",
        headers=admin_headers,
        json={"current_password": "wrong", "new_password": "new-password-1"},
    )
    assert response.status_code == 400


def test_forgot_password_does_not_leak_user_existence(client: TestClient, mail_outbox: list[EmailMessage]) -> None:
    known = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    unknown = client.post("/api/auth/forgot-password", json={"username": "nobody"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "accepted"}
    # The response is the same, but it is actually sent only for an existing account
    assert len(mail_outbox) == 1


def test_forgot_password_reports_when_mail_cannot_be_sent(
    client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Do not answer "sent" when it cannot be sent.

    With ``MAIL_ENABLED`` off it returned ``accepted``, so users waited for an email that
    would never arrive. That effectively removes the way to recover from being unable to log in.
    Whether a delivery method exists does not depend on the user, so a non-existent username
    gets the same response (existence does not leak).
    """
    with caplog.at_level(logging.WARNING):
        known = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
        unknown = client.post("/api/auth/forgot-password", json={"username": "nobody"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "mail_unavailable"}
    # Instead of email delivery, the link is in the log so an operator can hand it over
    assert db_session.scalar(select(PasswordResetToken)) is not None
    issued = [m for m in caplog.messages if m.startswith("password_reset_link_issued: ")]
    assert len(issued) == 1
    assert "/reset-password?token=" in issued[0]


def test_forgot_password_logs_a_link_that_actually_works(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """The link from the log alone is enough to recover the password (recovery path when mail is disabled)."""
    with caplog.at_level(logging.WARNING):
        client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})

    issued = next(m for m in caplog.messages if m.startswith("password_reset_link_issued: "))
    token = issued.split("token=", 1)[1]

    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "from-console-1"})
    assert reset.status_code == 200, reset.text

    signed_in = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": "from-console-1"},
    )
    assert signed_in.status_code == 200, signed_in.text


def test_forgot_password_reports_when_the_smtp_server_is_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Still returns guidance when SMTP is unreachable (it used to be a 500)."""
    monkeypatch.setenv("MAIL_ENABLED", "true")

    def _refuse(_self: SmtpEmailSender, _message: EmailMessage) -> None:
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(SmtpEmailSender, "send", _refuse)

    response = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    assert response.status_code == 200
    assert response.json() == {"status": "mail_unavailable"}


def test_forgot_password_while_smtp_is_down_does_not_leak_user_existence(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While SMTP is unreachable, an existing adult, a non-existent name and a child get the same response.

    Previously only an existing adult got ``mail_unavailable`` and everyone else got ``accepted``, so
    during an outage anyone could check from outside whether an adult username existed (task #768).
    """
    monkeypatch.setenv("MAIL_ENABLED", "true")

    def _refuse_send(_self: SmtpEmailSender, _message: EmailMessage) -> None:
        raise ConnectionRefusedError("smtp down")

    def _refuse_connect(_self: SmtpEmailSender) -> None:
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(SmtpEmailSender, "send", _refuse_send)
    monkeypatch.setattr(SmtpEmailSender, "check_reachable", _refuse_connect)
    db_session.add(User(username="kid", email=None, display_name="こども", password_hash="x", is_active=True))
    db_session.commit()

    adult = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    kid = client.post("/api/auth/forgot-password", json={"username": "kid"})
    nobody = client.post("/api/auth/forgot-password", json={"username": "nobody-here"})
    assert adult.status_code == kid.status_code == nobody.status_code == 200
    assert adult.json() == kid.json() == nobody.json() == {"status": "mail_unavailable"}


def test_forgot_password_without_email_answers_like_an_unknown_name(
    client: TestClient, db_session: Session, mail_outbox: list[EmailMessage]
) -> None:
    """An account without an email address (a child) gets the same response as a non-existent name.

    Otherwise anyone could check from outside whether a child's username exists (task #733).
    The screen always points to asking a parent (ADR-0011).
    """
    db_session.add(User(username="kid", email=None, display_name="こども", password_hash="x", is_active=True))
    db_session.commit()

    kid = client.post("/api/auth/forgot-password", json={"username": "kid"})
    nobody = client.post("/api/auth/forgot-password", json={"username": "nobody-here"})
    assert kid.status_code == nobody.status_code == 200
    assert kid.json() == nobody.json() == {"status": "accepted"}
    # There is nowhere to send it, so no token is issued either
    assert db_session.scalar(select(PasswordResetToken)) is None
    assert mail_outbox == []


def test_reset_password_with_valid_token(
    client: TestClient, db_session: Session, mail_outbox: list[EmailMessage]
) -> None:
    client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    row = db_session.scalar(select(PasswordResetToken))
    assert row is not None
    # The link is in the body and was actually sent
    assert "/reset-password?token=" in mail_outbox[0].body

    # Only the hash of the plaintext token is stored, so reissue one here to verify
    import hashlib
    import secrets

    token = secrets.token_urlsafe(32)
    row.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db_session.commit()

    response = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "reset-password-1"},
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin@example.com", "password": "reset-password-1"},
        ).status_code
        == 200
    )
    # Tokens are single-use
    again = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "another-password-1"},
    )
    assert again.status_code == 400


def test_reset_password_clears_a_pending_temporary_password(client: TestClient, db_session: Session) -> None:
    """Even mid temporary password, the user can recover via email.

    If the expiry were kept, the newly reset password would also be treated as expired.
    """
    import hashlib
    import secrets
    from datetime import timedelta

    from shared.kernel.timestamps import utcnow

    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    user.must_change_password = True
    user.temporary_password_expires_at = utcnow() - timedelta(seconds=1)
    token = secrets.token_urlsafe(32)
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    db_session.commit()

    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "recovered-pass-1"})
    assert reset.status_code == 200

    signed_in = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": "recovered-pass-1"},
    )
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["must_change_password"] is False


def test_reset_password_with_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/reset-password",
        json={"token": "bogus", "new_password": "whatever-123"},
    )
    assert response.status_code == 400


def test_inactive_user_cannot_login(client: TestClient, db_session: Session) -> None:
    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    user.is_active = False
    db_session.commit()
    response = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": master_data.DEFAULT_ADMIN_PASSWORD},
    )
    assert response.status_code == 401


def test_profile_update_changes_display_name_and_email(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put(
        "/api/auth/me",
        headers=admin_headers,
        json={"display_name": "  おとうさん  ", "email": "Dad@Example.com"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["display_name"] == "おとうさん"
    # Email addresses are normalized to lowercase (so the same address does not appear twice)
    assert data["email"] == "dad@example.com"
    # The login identifier does not change via the profile
    assert data["username"] == master_data.DEFAULT_ADMIN_USERNAME

    again = client.get("/api/auth/me", headers=admin_headers)
    assert again.json()["display_name"] == "おとうさん"


def test_profile_update_can_clear_email(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put("/api/auth/me", headers=admin_headers, json={"email": None})
    assert response.status_code == 200
    assert response.json()["email"] is None
    # Display name was not sent, so it does not change
    assert response.json()["display_name"] == master_data.DEFAULT_ADMIN_DISPLAY_NAME


def test_profile_update_rejects_email_used_by_another_account(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    db_session.add(
        User(
            username="mom",
            email="mom@example.com",
            display_name="mom",
            password_hash="x",
            is_active=True,
        )
    )
    db_session.commit()
    response = client.put("/api/auth/me", headers=admin_headers, json={"email": "mom@example.com"})
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "email_already_exists"


def test_login_rejects_unknown_username(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_credentials"
