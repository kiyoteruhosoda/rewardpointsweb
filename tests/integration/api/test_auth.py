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
    """期限切れの一時パスワードは通さないが、理由は伝える（ADR-0011）。

    ``invalid_credentials`` に丸めていたため、本人には「合っているはずのものが
    通らない」としか見えず、親へ再発行を頼めばよいと分からなかった。
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

    # 値を知らない相手には、これまでどおり何も明かさない
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
    # 応答は同じでも、実在するアカウントにだけ実際に送られている
    assert len(mail_outbox) == 1


def test_forgot_password_reports_when_mail_cannot_be_sent(
    client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """送れないのに「送りました」と返さない。

    ``MAIL_ENABLED`` が無効なまま ``accepted`` を返していたため、利用者は決して
    届かないメールを待っていた。ログインできない状態からの回復手段が、そこで
    事実上失われる。送信手段の有無は利用者に依らないので、実在しないユーザー名
    でも同じ応答になる（実在は漏れない）。
    """
    with caplog.at_level(logging.WARNING):
        known = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
        unknown = client.post("/api/auth/forgot-password", json={"username": "nobody"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "mail_unavailable"}
    # メールで届かない代わりに、運用者が手渡せるようリンクがログに出ている
    assert db_session.scalar(select(PasswordResetToken)) is not None
    issued = [m for m in caplog.messages if m.startswith("password_reset_link_issued: ")]
    assert len(issued) == 1
    assert "/reset-password?token=" in issued[0]


def test_forgot_password_logs_a_link_that_actually_works(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """ログに出たリンクだけでパスワードを取り戻せる（メール無効時の回復経路）。"""
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
    """SMTP に届かないときも案内を返す（以前は 500 になっていた）。"""
    monkeypatch.setenv("MAIL_ENABLED", "true")

    def _refuse(_self: SmtpEmailSender, _message: EmailMessage) -> None:
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(SmtpEmailSender, "send", _refuse)

    response = client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    assert response.status_code == 200
    assert response.json() == {"status": "mail_unavailable"}


def test_forgot_password_without_email_points_at_the_guardian(
    client: TestClient, db_session: Session, mail_outbox: list[EmailMessage]
) -> None:
    """メールアドレスを持たないアカウントには送れない（ADR-0011）。"""
    db_session.add(User(username="kid", email=None, display_name="こども", password_hash="x", is_active=True))
    db_session.commit()

    response = client.post("/api/auth/forgot-password", json={"username": "kid"})
    assert response.status_code == 200
    assert response.json() == {"status": "ask_guardian"}
    # 送る先が無いので、トークンも発行しない
    assert db_session.scalar(select(PasswordResetToken)) is None
    assert mail_outbox == []


def test_reset_password_with_valid_token(
    client: TestClient, db_session: Session, mail_outbox: list[EmailMessage]
) -> None:
    client.post("/api/auth/forgot-password", json={"username": master_data.DEFAULT_ADMIN_USERNAME})
    row = db_session.scalar(select(PasswordResetToken))
    assert row is not None
    # リンクは本文に載って実際に送られている
    assert "/reset-password?token=" in mail_outbox[0].body

    # 平文トークンはハッシュしか保存されないため、ここで発行し直して検証する
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
    # トークンは使い捨て
    again = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "another-password-1"},
    )
    assert again.status_code == 400


def test_reset_password_clears_a_pending_temporary_password(client: TestClient, db_session: Session) -> None:
    """一時パスワードの途中でも、本人がメールから取り戻せる。

    期限を残すと、再設定した新しいパスワードまで期限切れ扱いになってしまう。
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
    # メールアドレスは小文字へ正規化する（同じアドレスが 2 つ並ばないように）
    assert data["email"] == "dad@example.com"
    # ログイン識別子はプロフィールでは変わらない
    assert data["username"] == master_data.DEFAULT_ADMIN_USERNAME

    again = client.get("/api/auth/me", headers=admin_headers)
    assert again.json()["display_name"] == "おとうさん"


def test_profile_update_can_clear_email(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put("/api/auth/me", headers=admin_headers, json={"email": None})
    assert response.status_code == 200
    assert response.json()["email"] is None
    # 表示名は送っていないので変わらない
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
