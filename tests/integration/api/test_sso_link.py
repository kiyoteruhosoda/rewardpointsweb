"""本人の操作で IdP の口座と結び付ける導線（ADR-0036）。

ログインの往復（``test_sso_login``）と同じ ``/callback`` で戻ってくるが、後始末が
違う。ここで確かめるのは

- 始めるには**入っていること**が要る（未認証は 401）
- 戻りの結び付け先は**往復を始めた利用者**で、いまのセッションではない
- 断りはログイン画面ではなく**設定画面**へ返る（押した人は入ったまま）
- 外すと入れなくなる利用者は断る

の 4 つ。
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

from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    AuthorizationRequest,
    CodeExchange,
)
from bounded_contexts.identity_federation.presentation import dependencies
from shared.domain.auth import master_data
from shared.infrastructure.models import User

ISSUER = "https://idp.example"


@dataclass
class FakeGateway:
    subject: str = "idp-subject-1"
    seen: list[CodeExchange] = field(default_factory=list)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        return f"{ISSUER}/authorize?state={request.state}&nonce={request.nonce}"

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        self.seen.append(exchange)
        return {
            "sub": self.subject,
            "nonce": exchange.nonce,
            "email": "admin@example.com",
            "email_verified": True,
            "name": "管理者",
        }


@pytest.fixture
def sso_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", "rewardpointsweb")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example/api/auth/sso/callback")


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def sso_client(app: FastAPI, gateway: FakeGateway, sso_settings: None) -> Iterator[TestClient]:
    app.dependency_overrides[dependencies.oidc_gateway] = lambda: gateway
    with TestClient(app, follow_redirects=False) as client:
        yield client
    app.dependency_overrides.clear()


def _sign_in(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={
            "username": master_data.DEFAULT_ADMIN_USERNAME,
            "password": master_data.DEFAULT_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _start_link(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/auth/sso/link/start", headers=headers)
    assert response.status_code == 200, response.text
    url = str(response.json()["authorization_url"])
    assert url.startswith(f"{ISSUER}/authorize")
    return str(parse_qs(urlparse(url).query)["state"][0])


def _callback(client: TestClient, state: str) -> str:
    response = client.get("/api/auth/sso/callback", params={"code": "c", "state": state})
    assert response.status_code == 303, response.text
    return str(response.headers["location"])


def test_starting_a_link_requires_being_signed_in(sso_client: TestClient) -> None:
    assert sso_client.post("/api/auth/sso/link/start").status_code == 401


def test_a_completed_round_trip_links_the_identity(sso_client: TestClient) -> None:
    headers = _sign_in(sso_client)
    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["linked"] is False

    assert _callback(sso_client, _start_link(sso_client, headers)) == "/security?sso_link=linked"

    body = sso_client.get("/api/auth/sso/link", headers=headers).json()
    assert body["linked"] is True
    assert body["linked_at"].endswith("Z")
    # 管理者はパスワードを持っているので、外しても入り口が残る。
    assert body["can_unlink"] is True


def test_the_identity_is_not_linked_after_signing_out(sso_client: TestClient) -> None:
    """⚠ 往復の途中で入れ替わったブラウザで、誰かの口座へ結び付けない。"""
    headers = _sign_in(sso_client)
    state = _start_link(sso_client, headers)
    sso_client.cookies.clear()

    assert _callback(sso_client, state) == "/security?sso_link_error=sso_link_session_mismatch"


def test_a_second_account_at_the_same_provider_is_refused(sso_client: TestClient, gateway: FakeGateway) -> None:
    """既にある結び付きを黙って差し替えない（前の入り口が予告なく消える）。"""
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))

    gateway.subject = "another-subject"
    assert _callback(sso_client, _start_link(sso_client, headers)) == ("/security?sso_link_error=sso_already_linked")


def test_a_link_can_be_removed_while_a_password_remains(sso_client: TestClient) -> None:
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))

    assert sso_client.delete("/api/auth/sso/link", headers=headers).status_code == 200
    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["linked"] is False
    # 2 回目は「結び付いていない」。
    assert sso_client.delete("/api/auth/sso/link", headers=headers).status_code == 404


def test_the_last_entrance_is_not_removed(sso_client: TestClient, engine: sa.Engine) -> None:
    """⚠ パスワードもパスキーも無い利用者からは外させない（締め出しになる）。"""
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))
    _drop_password(engine)

    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["can_unlink"] is False
    refused = sso_client.delete("/api/auth/sso/link", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"]["error"] == "sso_last_entrance"


def _drop_password(engine: sa.Engine) -> None:
    """ローカルのパスワードを落とす（IdP でしか入れない利用者にする。ADR-0034）。"""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = session.scalars(sa.select(User).where(User.username == master_data.DEFAULT_ADMIN_USERNAME)).one()
    user.password_hash = None
    session.commit()
    session.close()
