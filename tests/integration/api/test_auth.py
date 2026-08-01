from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

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


def test_forgot_password_does_not_leak_user_existence(client: TestClient) -> None:
    known = client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "accepted"}


def test_reset_password_with_valid_token(client: TestClient, db_session: Session) -> None:
    # メール送信は無効のためトークンは DB から直接取り出して検証する
    client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    row = db_session.scalar(select(PasswordResetToken))
    assert row is not None

    # 平文トークンはハッシュしか保存されないため、サービスを直接使って発行し直す
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
