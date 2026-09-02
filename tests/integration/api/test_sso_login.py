"""SSO ログインの往復（ADR-0029）。

IdP との通信はゲートウェイを差し替えて止める。ここで確かめるのは**このアプリ側の
組み立て**——控えの往復、ブラウザの結び付け、引き換え券、そして「利用者を作らない」
という一点。
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

from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    AuthorizationRequest,
    CodeExchange,
)
from bounded_contexts.identity_federation.presentation import dependencies
from bounded_contexts.identity_federation.presentation.router import SSO_BINDING_COOKIE
from shared.infrastructure.models import User

ISSUER = "https://idp.example"
CLIENT_ID = "rewardpointsweb"
SUBJECT = "idp-subject-1"
EMAIL = "parent@example.com"


@dataclass
class FakeGateway:
    """IdP の代わり。受け取った要求を控え、決まったクレームを返す。"""

    claims: dict[str, Any]
    seen: list[CodeExchange] = field(default_factory=list)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        return f"{ISSUER}/authorize?state={request.state}&nonce={request.nonce}"

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        self.seen.append(exchange)
        return {"sub": SUBJECT, "nonce": exchange.nonce, **self.claims}


@pytest.fixture
def sso_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example/api/auth/sso/callback")


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway(claims={"email": EMAIL, "email_verified": True, "name": "親"})


@pytest.fixture
def sso_client(
    app: FastAPI,
    gateway: FakeGateway,
    sso_settings: None,
) -> Iterator[TestClient]:
    app.dependency_overrides[dependencies.oidc_gateway] = lambda: gateway
    # IdP からの戻りは 303 の連なりで、追いかけると Location を確かめられない
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


def _start(client: TestClient, redirect_to: str = "/families") -> str:
    """送り出しまで進め、控えの ``state`` を返す。"""
    response = client.get("/api/auth/sso/login", params={"redirect_to": redirect_to})
    assert response.status_code == 303, response.text
    assert SSO_BINDING_COOKIE in response.cookies
    state = parse_qs(urlparse(response.headers["location"]).query)["state"]
    return str(state[0])


def _callback(client: TestClient, state: str) -> str:
    """戻りまで進め、SPA へ渡された引き換え券を返す。"""
    response = client.get("/api/auth/sso/callback", params={"code": "authorization-code", "state": state})
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/login/sso?ticket=")
    return str(parse_qs(urlparse(location).query)["ticket"][0])


def test_provider_is_advertised_without_leaking_where_it_is(sso_client: TestClient) -> None:
    body = sso_client.get("/api/auth/sso/provider").json()

    assert body == {"enabled": True, "display_name": "SSO"}


def test_provider_is_off_when_sso_is_not_configured(client: TestClient) -> None:
    assert client.get("/api/auth/sso/provider").json()["enabled"] is False


def test_signs_in_an_existing_user_and_returns_to_where_it_started(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    ticket = _callback(sso_client, _start(sso_client))

    session = sso_client.post("/api/auth/sso/token", json={"ticket": ticket})

    assert session.status_code == 200, session.text
    body = session.json()
    assert body["redirect_to"] == "/families"
    assert body["must_change_password"] is False
    # 発行したトークンは本人のもの
    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == parent
    # PKCE の検証値と nonce は控えのものが渡っている
    assert gateway.seen[0].code_verifier
    assert gateway.seen[0].nonce


def test_the_second_sign_in_goes_through_the_stored_link(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    """1 度結び付けば、IdP 側でメールアドレスが変わっても入れる。"""
    sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))})

    gateway.claims = {"email": "renamed@example.com", "email_verified": True, "name": "親"}
    body = sso_client.post(
        "/api/auth/sso/token",
        json={"ticket": _callback(sso_client, _start(sso_client))},
    ).json()

    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == parent


def test_an_unknown_address_does_not_create_a_user(sso_client: TestClient, engine: sa.Engine) -> None:
    """SSO は既に居る人の入り口。名乗られただけでアカウントは増えない。"""
    before = _user_count(engine)

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_account_not_linked"
    assert _user_count(engine) == before


def test_an_unverified_address_is_refused(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    gateway.claims = {"email": EMAIL, "email_verified": False}

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_account_not_linked"


def test_a_callback_from_another_browser_is_refused(sso_client: TestClient, parent: int) -> None:
    """攻撃者が始めた認可要求を踏まされても、被害者は攻撃者としてログインしない。"""
    state = _start(sso_client)
    sso_client.cookies.delete(SSO_BINDING_COOKIE)

    response = sso_client.get("/api/auth/sso/callback", params={"code": "c", "state": state})

    assert response.headers["location"] == "/login?sso_error=sso_state_invalid"


def test_the_authorization_request_is_good_for_one_callback(sso_client: TestClient, parent: int) -> None:
    state = _start(sso_client)
    _callback(sso_client, state)

    response = sso_client.get("/api/auth/sso/callback", params={"code": "c", "state": state})

    assert response.headers["location"] == "/login?sso_error=sso_state_invalid"


def test_the_ticket_is_good_for_one_exchange(sso_client: TestClient, parent: int) -> None:
    ticket = _callback(sso_client, _start(sso_client))
    assert sso_client.post("/api/auth/sso/token", json={"ticket": ticket}).status_code == 200

    again = sso_client.post("/api/auth/sso/token", json={"ticket": ticket})

    assert again.status_code == 401
    assert again.json()["detail"]["error"] == "sso_ticket_invalid"


def test_an_error_from_the_idp_is_reflected_only_when_it_is_a_plain_code(sso_client: TestClient) -> None:
    """IdP のエラーコードはそのまま画面の URL へ載る。素性の分かる形だけを通す。"""
    plain = sso_client.get("/api/auth/sso/callback", params={"error": "access_denied"})
    crafted = sso_client.get("/api/auth/sso/callback", params={"error": "https://phishing.example"})

    assert plain.headers["location"] == "/login?sso_error=access_denied"
    assert crafted.headers["location"] == "/login?sso_error=sso_error"


def test_an_outside_redirect_target_falls_back_to_the_entrance(sso_client: TestClient, parent: int) -> None:
    ticket = _callback(sso_client, _start(sso_client, redirect_to="https://phishing.example"))

    body = sso_client.post("/api/auth/sso/token", json={"ticket": ticket}).json()

    assert body["redirect_to"] == "/"


def test_a_disabled_user_cannot_get_in_through_the_idp(
    sso_client: TestClient,
    engine: sa.Engine,
    parent: int,
) -> None:
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = session.get(User, parent)
    assert user is not None
    user.is_active = False
    session.commit()
    session.close()

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "c", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_account_inactive"


def _user_count(engine: sa.Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(sa.select(sa.func.count()).select_from(User.__table__)).scalar_one())
