"""Whether stop propagation (IdP -> RP) works (ADR-0032).

Communication with the IdP is cut by swapping the gateway. What we want to confirm here is that **a received
notice actually ends the session**, and that it does not get the scope of what it ends wrong.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
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
    """An IdP that just returns the ID token and ``logout_token`` as verified claims.

    ``logout_token`` is spelled as "``<sid>|<jti>``". **Signature verification is the
    Infrastructure layer's responsibility**, so it is not imitated here.
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
    # Link to an existing user (how linking works is not the subject of this test).
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
    """An existing user with an email address (the account SSO links to)."""
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
    """Sign in with SSO (authorization request -> callback -> code exchange)."""
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
    """The path the IdP server calls. **It carries no cookie and no credentials.**"""
    return client.post(LOGOUT, data={"logout_token": logout_token}).status_code


def _legacy_refresh_of(session: dict[str, Any]) -> str:
    """Build the SSO login refresh token issued before this mechanism (ADR-0058) (same subject and time)."""
    claims = jwt.decode(
        session["access_token"],
        settings.jwt_secret_key,
        algorithms=["HS256"],
        audience=settings.access_token_audience,
        issuer=settings.access_token_issuer,
    )
    claims["type"] = "refresh"
    claims["exp"] = int(claims["exp"]) + 3600
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


def _refresh(client: TestClient, session: dict[str, Any]) -> int:
    """Whether there is a way to extend. An SSO login holds no refresh token (ADR-0058); it continues only by
    asking the IdP (which refuses if stopped). The refresh endpoint also refuses tokens from the old mechanism."""
    assert session["refresh_token"] is None
    return client.post("/api/auth/refresh", json={"refresh_token": _legacy_refresh_of(session)}).status_code


def test_a_stop_from_the_idp_ends_the_session_at_the_next_refresh(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200

    assert _post_logout(sso_client, "session-1|delivery-1") == 200

    # ⚠ **The access token in hand keeps working until it expires** (ADR-0037; verification does not hit the DB).
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200
    # It ends at the next refresh.
    assert _refresh(sso_client, session) == 401


def test_the_access_token_outlives_the_stop_only_until_it_expires(sso_client: TestClient, parent: int) -> None:
    """⚠ **This is the looseness we accepted** (ADR-0037)."""
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200
    assert settings.access_token_expires_seconds <= 300


def test_a_stopped_session_cannot_be_refreshed(sso_client: TestClient, parent: int) -> None:
    """⚠ Without this, passing a single refresh would be enough to slip past the stop."""
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    assert _refresh(sso_client, session) == 401


def test_a_stop_for_another_session_leaves_this_one_alone(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-2|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200


def test_a_stop_without_a_sid_ends_every_session_of_that_user(sso_client: TestClient, parent: int) -> None:
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "|delivery-1") == 200
    assert _refresh(sso_client, session) == 401


def test_signing_in_again_after_a_stop_works(sso_client: TestClient, gateway: FakeGateway, parent: int) -> None:
    """What gets stopped is **that session**, not the user."""
    _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "|delivery-1") == 200
    gateway.sid = "session-2"
    again = _sign_in_with_sso(sso_client)
    assert sso_client.get("/api/auth/me", headers=_bearer(again)).status_code == 200


def test_a_resent_notice_is_accepted_but_changes_nothing(sso_client: TestClient, parent: int) -> None:
    """The sender reuses the same ``jti`` on resend (idp ADR-0024).

    ⚠ **Without rejecting it, a resend of an old notice could kill "a session that is alive now"**
    -- here it is made the worst case by assuming an IdP that reuses the same ``sid``.
    """
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    session = _sign_in_with_sso(sso_client)
    assert _post_logout(sso_client, "session-1|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=_bearer(session)).status_code == 200


def test_a_local_login_is_not_touched(sso_client: TestClient, admin_headers: dict[str, str], parent: int) -> None:
    """Stop propagation can only end sessions that started via the IdP (ADR-0032)."""
    assert _post_logout(sso_client, "|delivery-1") == 200
    assert sso_client.get("/api/auth/me", headers=admin_headers).status_code == 200


def test_a_token_that_does_not_verify_is_refused(sso_client: TestClient, gateway: FakeGateway) -> None:
    gateway.rejected.add("forged")
    assert _post_logout(sso_client, "forged") == 400


def test_a_request_without_the_token_is_refused(sso_client: TestClient) -> None:
    assert sso_client.post(LOGOUT, data={"something_else": "x"}).status_code == 400
