"""SSO で入ったログインはリフレッシュトークンを持たず、切れたら画面を出さずに続ける（ADR-0058）。

IdP との通信はゲートウェイを差し替えて止める。続ける往復は、画面が見えない枠で開く
``/api/auth/sso/renew`` から始まり、戻り（``/callback``）が引き換え券を付けて結果の頁へ送る。
画面は券を ``POST /api/auth/sso/token``（``continuing: true``）でトークンへ換える。
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.security import generate_password_hash

from bounded_contexts.identity_federation.domain.exceptions import InvalidIdTokenError
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    AuthorizationRequest,
    CodeExchange,
    LogoutTokenVerification,
)
from bounded_contexts.identity_federation.presentation import dependencies
from presentation.fastapi.services.token_service import RENEWAL_CARRY_SECONDS, TokenService
from shared.infrastructure.models import User
from shared.kernel.settings.settings import settings

ISSUER = "https://idp.example"
SUBJECT = "idp-subject-1"
EMAIL = "parent@example.com"
RENEWED = "/api/auth/sso/renewed"


@dataclass
class FakeGateway:
    """ID トークンを、検証済みのクレームとして返すだけの IdP。送り出した要求を覚える。"""

    requests: list[AuthorizationRequest] = field(default_factory=list)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        self.requests.append(request)
        return f"{ISSUER}/authorize?state={request.state}&nonce={request.nonce}"

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        if exchange.code != "authorization-code":
            raise InvalidIdTokenError
        return {
            "sub": SUBJECT,
            "nonce": exchange.nonce,
            "email": EMAIL,
            "email_verified": True,
            "name": "親",
            "sid": "session-1",
        }

    def verify_logout_token(self, verification: LogoutTokenVerification) -> Mapping[str, Any]:  # pragma: no cover
        raise NotImplementedError


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def sso_client(app: FastAPI, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", "rewardpointsweb")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example/api/auth/sso/callback")
    monkeypatch.setenv("OIDC_LINK_BY_EMAIL", "true")
    app.dependency_overrides[dependencies.oidc_gateway] = lambda: gateway
    with TestClient(app, follow_redirects=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def parent(engine: sa.Engine) -> int:
    """メールアドレスを持つ既存の利用者（SSO で寄せる先）。"""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(username="parent", email=EMAIL, display_name="親", password_hash=generate_password_hash("password"))
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def _state_of(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


def _sign_in_with_sso(client: TestClient) -> dict[str, Any]:
    start = client.get("/api/auth/sso/login", params={"redirect_to": "/families"})
    callback = client.get(
        "/api/auth/sso/callback", params={"code": "authorization-code", "state": _state_of(start.headers["location"])}
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    response = client.post("/api/auth/sso/token", json={"ticket": ticket})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _renew(client: TestClient, params: dict[str, str] | None = None) -> Any:
    """続ける往復（枠の中で開く口 → IdP → 戻り）。戻りの応答を返す。"""
    start = client.get("/api/auth/sso/renew")
    assert start.status_code == 303, start.text
    query = {"code": "authorization-code", **(params or {}), "state": _state_of(start.headers["location"])}
    return client.get("/api/auth/sso/callback", params=query)


def _result_of(response: Any) -> dict[str, str]:
    location = response.headers["location"]
    assert location.startswith(f"{RENEWED}?")
    return {key: values[0] for key, values in parse_qs(urlparse(location).query).items()}


def _claims(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=["HS256"],
        audience=settings.access_token_audience,
        issuer=settings.access_token_issuer,
        options={"verify_exp": False},
    )


def _bearer_of(claims: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt.encode(claims, settings.jwt_secret_key, algorithm='HS256')}"}


def _expired(session: dict[str, Any], *, ago: timedelta = timedelta(minutes=10)) -> dict[str, Any]:
    claims = _claims(session["access_token"])
    claims["exp"] = int((datetime.now(UTC) - ago).timestamp())
    return claims


def test_an_sso_login_hands_out_no_refresh_token(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert session["refresh_token"] is None
    assert session["access_token"]


def test_a_password_login_still_refreshes(sso_client: TestClient, engine: sa.Engine, parent: int) -> None:
    """パスワード・パスキーで入ったログインは変えない（IdP に問い合わせる先が無い）。"""
    with Session(engine) as db:
        user = db.get(User, parent)
        assert user is not None
        pair = TokenService.create_token_pair(user)
    assert pair["refresh_token"]
    assert sso_client.post("/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 200


def test_renewing_asks_the_idp_without_a_screen(sso_client: TestClient, gateway: FakeGateway) -> None:
    start = sso_client.get("/api/auth/sso/renew")
    assert start.status_code == 303
    assert start.headers["location"].startswith(f"{ISSUER}/authorize")
    assert gateway.requests[-1].silent is True
    assert start.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in start.headers["content-security-policy"]


def test_renewing_hands_a_ticket_to_the_result_page(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    renewed = _renew(sso_client)
    assert renewed.status_code == 303
    assert renewed.headers["x-frame-options"] == "SAMEORIGIN"
    result = _result_of(renewed)
    assert result["result"] == "renewed"
    exchanged = sso_client.post(
        "/api/auth/sso/token",
        json={"ticket": result["ticket"], "continuing": True},
        headers=_bearer_of(_expired(session)),
    )
    assert exchanged.status_code == 200, exchanged.text
    assert exchanged.json()["refresh_token"] is None
    assert _claims(exchanged.json()["access_token"])["sub"] == str(parent)
    # 券は 1 回限り
    assert (
        sso_client.post("/api/auth/sso/token", json={"ticket": result["ticket"], "continuing": True}).status_code == 401
    )


def test_renewing_without_a_previous_token_signs_in_afresh(sso_client: TestClient, parent: int) -> None:
    result = _result_of(_renew(sso_client))
    exchanged = sso_client.post("/api/auth/sso/token", json={"ticket": result["ticket"], "continuing": True})
    assert exchanged.status_code == 200


def test_renewing_is_refused_when_someone_else_comes_back(sso_client: TestClient, parent: int) -> None:
    """IdP で別の人に入り直していたら続けない。開いている画面は前の人のものだから。"""
    other = _expired(_sign_in_with_sso(sso_client))
    other["sub"] = str(parent + 1000)
    result = _result_of(_renew(sso_client))
    refused = sso_client.post(
        "/api/auth/sso/token", json={"ticket": result["ticket"], "continuing": True}, headers=_bearer_of(other)
    )
    assert refused.status_code == 401
    assert refused.json()["detail"]["error"] == "sso_renewal_switched_user"


def test_an_ordinary_login_ignores_a_stale_token_of_someone_else(sso_client: TestClient, parent: int) -> None:
    """ボタンで入り直すときは、手元に別の人の古いトークンが残っていても入れる。"""
    other = _expired(_sign_in_with_sso(sso_client))
    other["sub"] = str(parent + 1000)
    start = sso_client.get("/api/auth/sso/login", params={"redirect_to": "/families"})
    callback = sso_client.get(
        "/api/auth/sso/callback", params={"code": "authorization-code", "state": _state_of(start.headers["location"])}
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    assert sso_client.post("/api/auth/sso/token", json={"ticket": ticket}, headers=_bearer_of(other)).status_code == 200


def test_renewing_is_declined_when_the_idp_has_no_session(sso_client: TestClient) -> None:
    assert _result_of(_renew(sso_client, {"error": "login_required"})) == {"result": "declined"}


def test_a_broken_return_fails(sso_client: TestClient) -> None:
    assert _result_of(_renew(sso_client, {"error": "server_error"})) == {"result": "failed"}
    assert _result_of(_renew(sso_client, {"code": "wrong-code"})) == {"result": "failed"}


def test_the_result_page_may_only_be_framed_by_this_origin(sso_client: TestClient) -> None:
    page = sso_client.get(RENEWED, params={"result": "renewed", "ticket": "x"})
    assert page.status_code == 200
    assert page.headers["x-frame-options"] == "SAMEORIGIN"
    assert page.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'self'"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert page.headers["cache-control"] == "no-store"


def test_an_expired_token_carries_the_session_only_within_the_window(sso_client: TestClient, parent: int) -> None:
    stale = _expired(_sign_in_with_sso(sso_client), ago=timedelta(seconds=RENEWAL_CARRY_SECONDS + 60))
    stale["sub"] = str(parent + 1000)
    result = _result_of(_renew(sso_client))
    # 古すぎて読まない ——別の人のトークンでも、新しいログインとして入る（断らない）
    exchanged = sso_client.post(
        "/api/auth/sso/token", json={"ticket": result["ticket"], "continuing": True}, headers=_bearer_of(stale)
    )
    assert exchanged.status_code == 200
