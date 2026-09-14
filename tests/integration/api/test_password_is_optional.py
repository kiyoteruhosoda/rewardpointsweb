"""「ローカル認証を持たない」をデータで表せているか（ADR-0034）。

``users.password_hash`` が NULL の利用者は、パスワードで入れない・変更できない・
**リセットでも生やせない**。持たせられるのは管理者が明示的に設定したときだけ。
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
    """SSO でしか入れない利用者（パスワードを持たない）。"""
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
    """⚠ ここが抜けると、リセット 1 回でローカル認証が生える。"""
    response = client.post("/api/auth/forgot-password", json={"username": _SSO_ONLY})
    # 応答は宛先が無いときと同じ（存在を漏らさない）。
    assert response.status_code == 200
    assert db_session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == sso_only_user)) is None


def _take_the_password_away(db_session: Session, username: str) -> None:
    """入っている人のパスワードだけを取り上げる（トークンはそのまま）。"""
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    user.password_hash = None
    db_session.commit()


def test_the_screen_is_told_whether_there_is_a_password(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """画面はこれを見て、パスワード変更の導線を出すかどうかを決める。"""
    assert client.get("/api/auth/me", headers=admin_headers).json()["has_password"] is True

    _take_the_password_away(db_session, master_data.DEFAULT_ADMIN_USERNAME)
    assert client.get("/api/auth/me", headers=admin_headers).json()["has_password"] is False


def test_a_user_without_a_password_cannot_change_one(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """パスワードを持たない利用者に「今のパスワード」は入力できない。

    理由は分けずに揃える（入り口の有無を外から数えられないようにするため）。
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
    """ローカル口座を持たせるのは、明示的な操作だけ（ADR-0034）。"""
    updated = client.put(
        f"/api/admin/users/{sso_only_user}",
        headers=admin_headers,
        json={"password": "given-on-purpose-1"},
    )
    assert updated.status_code == 200, updated.text
    signed_in = client.post("/api/auth/login", json={"username": _SSO_ONLY, "password": "given-on-purpose-1"})
    assert signed_in.status_code == 200, signed_in.text
