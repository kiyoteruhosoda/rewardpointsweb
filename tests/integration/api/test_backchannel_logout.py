"""停止の伝播（IdP → RP）が効いているか（ADR-0032）。

IdP との通信はゲートウェイを差し替えて止める。ここで確かめたいのは、**届いた通知が
実際にセッションを終わらせること**と、終わらせる範囲を間違えないことである。
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.security import generate_password_hash

from bounded_contexts.identity_federation.domain.exceptions import (
    InvalidLogoutTokenError,
)
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    AuthorizationRequest,
    CodeExchange,
    LogoutTokenVerification,
)
from bounded_contexts.identity_federation.domain.value_objects.logout_notice import (
    LOGOUT_EVENT,
)
from bounded_contexts.identity_federation.presentation import dependencies
from shared.infrastructure.models import User
from shared.kernel.settings.settings import settings

ISSUER = "https://idp.example"
CLIENT_ID = "rewardpointsweb"
SUBJECT = "idp-subject-1"
EMAIL = "parent@example.com"
LOGOUT = "/api/auth/sso/backchannel-logout"


@dataclass
class FakeGateway:
    """ID トークンと ``logout_token`` を、検証済みのクレームとして返すだけの IdP。

    ``logout_token`` は「``<sid>|<jti>``」という綴りにする。**署名の検証は
    Infrastructure 層の責任**なので、ここではそこを模さない。
    """

    sid: str = "session-1"
    rejected: set[str] = field(default_factory=set)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        return f"{ISSUER}/authorize?state={request.state}&nonce={request.nonce}"

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        return {
            "sub": SUBJECT,
            "nonce": exchange.nonce,
            "email": EMAIL,
            "email_verified": True,
            "name": "親",
            "sid": self.sid,
        }

    def verify_logout_token(self, verification: LogoutTokenVerification) -> Mapping[str, Any]:
        token = verification.logout_token
        if token in self.rejected:
            raise InvalidLogoutTokenError
        sid, _, jti = token.partition("|")
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": verification.provider.client_id,
            "sub": SUBJECT,
            "jti": jti,
            "events": {LOGOUT_EVENT: {}},
        }
        if sid:
            claims["sid"] = sid
        return claims


@pytest.fixture
def sso_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example/api/auth/sso/callback")
    # 既存の利用者へ寄せる（この試験の主題は結び付け方ではない）。
    monkeypatch.setenv("OIDC_LINK_BY_EMAIL", "true")


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def sso_client(app: FastAPI, gateway: FakeGateway, sso_settings: None) -> Iterator[TestClient]:
    app.dependency_overrides[dependencies.oidc_gateway] = lambda: gateway
    with TestClient(app, follow_redirects=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def parent(engine: sa.Engine) -> int:
    """メールアドレスを持つ既存の利用者（SSO で寄せる先）。"""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(
        username="parent",
        email=EMAIL,
        display_name="親",
        password_hash=generate_password_hash("password"),
    )
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def _sign_in_with_sso(client: TestClient) -> dict[str, Any]:
    """SSO で入る（認可要求 → 戻り → 券の引き換え）。"""
    start = client.get("/api/auth/sso/login", params={"redirect_to": "/families"})
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    callback = client.get("/api/auth/sso/callback", params={"code": "authorization-code", "state": state})
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    response = client.post("/api/auth/sso/token", json={"ticket": ticket})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _bearer(body: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {body['access_token']}"}


def _post_logout(client: TestClient, logout_token: str) -> int:
    """IdP のサーバーが叩く経路。**Cookie も資格情報も持たない。**"""
    return client.post(LOGOUT, data={"logout_token": logout_token}).status_code


def _refresh(client: TestClient, session: dict[str, Any]) -> int:
    """更新を 1 回通す。⚠ **止める判定はここに集約してある**（ADR-0037）。"""
    return client.post("/api/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code


def test_a_stop_from_the_idp_ends_the_session_at_the_next_refresh(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200

    assert _post_logout(sso_client, "session-1|delivery-1") == 200

    # ⚠ **手元のアクセストークンは寿命まで通る**（ADR-0037。検証は DB を引かない）。
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200
    # 終わるのは更新のとき。
    assert _refresh(sso_client, session) == 401


def test_the_access_token_outlives_the_stop_only_until_it_expires(sso_client: TestClient, parent: int) -> None:
    """⚠ **これが引き受けた緩さである**（ADR-0037）。"""
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200
    assert settings.access_token_expires_seconds <= 300


def test_a_stopped_session_cannot_be_refreshed(sso_client: TestClient, parent: int) -> None:
    """⚠ ここが抜けると、更新を 1 回通すだけで停止をすり抜けられる。"""
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    refreshed = sso_client.post("/api/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refreshed.status_code == 401, refreshed.text


def test_a_stop_for_another_session_leaves_this_one_alone(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-2|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200


def test_a_stop_without_a_sid_ends_every_session_of_that_user(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "|delivery-1") == 200
    assert _refresh(sso_client, session) == 401


def test_signing_in_again_after_a_stop_works(sso_client: TestClient, gateway: FakeGateway, parent: int) -> None:
    """止めるのは**そのときのセッション**であって、利用者ではない。"""
    _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "|delivery-1") == 200
    gateway.sid = "session-2"
    again = _sign_in_with_sso(sso_client)
    assert sso_client.get("/api/auth/me", headers=_bearer(again)).status_code == 200


def test_a_resent_notice_is_accepted_but_changes_nothing(sso_client: TestClient, parent: int) -> None:
    """送り手は再送でも同じ ``jti`` を使う（idp の ADR-0024）。

    ⚠ **弾かないと、古い通知の再送で「いま生きているセッション」を落とせる**
    ——ここでは、同じ ``sid`` を使い回す IdP を想定して最悪の形にしてある。
    """
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200


def test_a_local_login_is_not_touched(sso_client: TestClient, admin_headers: dict[str, str], parent: int) -> None:
    """停止の伝播が消せるのは IdP 経由で始まったセッションだけ（ADR-0032）。"""
    assert _post_logout(sso_client, "|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=admin_headers).status_code == 200


def test_a_token_that_does_not_verify_is_refused(sso_client: TestClient, gateway: FakeGateway) -> None:
    gateway.rejected.add("forged")
    assert _post_logout(sso_client, "forged") == 400


def test_a_request_without_the_token_is_refused(sso_client: TestClient) -> None:
    assert sso_client.post(LOGOUT, data={"something_else": "x"}).status_code == 400
