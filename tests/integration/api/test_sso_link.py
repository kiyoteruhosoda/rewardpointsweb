"""The user-initiated flow that links an IdP account (ADR-0036).

It comes back through the same ``/callback`` as the login round trip (``test_sso_login``), but the
follow-up differs. This checks:

- Starting requires **being signed in** (unauthenticated is 401)
- The link target on return is **the user who started the round trip**, not the current session
- Rejections go back to the **settings screen**, not the login screen (the user stays signed in)
- Unlinking is refused for a user who would then be unable to sign in

These are the 4 checks.
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
    #: The ``acr`` to return. ⚠ **Not returned by default** -- that is how it looks when not requested (ADR-0039).
    acr: str | None = None
    seen: list[CodeExchange] = field(default_factory=list)
    sent: list[AuthorizationRequest] = field(default_factory=list)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        self.sent.append(request)
        return f"{ISSUER}/authorize?state={request.state}&nonce={request.nonce}"

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        self.seen.append(exchange)
        claims: dict[str, Any] = {
            "sub": self.subject,
            "nonce": exchange.nonce,
            "email": "admin@example.com",
            "email_verified": True,
            "name": "管理者",
        }
        if self.acr is not None:
            claims["acr"] = self.acr
        return claims


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
def required_acr(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ **If requested, it is verified** (ADR-0039). Switches to the requiring mode."""
    monkeypatch.setenv("OIDC_ACR_VALUES", '["urn:assay:ac:mfa"]')


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
    # The admin has a password, so an entry point remains after unlinking.
    assert body["can_unlink"] is True


def test_the_identity_is_not_linked_after_signing_out(sso_client: TestClient) -> None:
    """⚠ Do not link someone's account in a browser that was swapped mid round trip."""
    headers = _sign_in(sso_client)
    state = _start_link(sso_client, headers)
    sso_client.cookies.clear()

    assert _callback(sso_client, state) == "/security?sso_link_error=sso_link_session_mismatch"


def test_a_second_account_at_the_same_provider_is_refused(sso_client: TestClient, gateway: FakeGateway) -> None:
    """Do not silently replace an existing link (the previous entry point would vanish without notice)."""
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))

    gateway.subject = "another-subject"
    assert _callback(sso_client, _start_link(sso_client, headers)) == ("/security?sso_link_error=sso_already_linked")


def test_a_link_can_be_removed_while_a_password_remains(sso_client: TestClient) -> None:
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))

    assert sso_client.delete("/api/auth/sso/link", headers=headers).status_code == 200
    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["linked"] is False
    # The second time it is "not linked".
    assert sso_client.delete("/api/auth/sso/link", headers=headers).status_code == 404


def test_the_last_entrance_is_not_removed(sso_client: TestClient, engine: sa.Engine) -> None:
    """⚠ Do not let a user with neither a password nor a passkey unlink (that would lock them out)."""
    headers = _sign_in(sso_client)
    _callback(sso_client, _start_link(sso_client, headers))
    _drop_password(engine)

    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["can_unlink"] is False
    refused = sso_client.delete("/api/auth/sso/link", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"]["error"] == "sso_last_entrance"


def _drop_password(engine: sa.Engine) -> None:
    """Drop the local password (making a user who can only sign in via the IdP. ADR-0034)."""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = session.scalars(sa.select(User).where(User.username == master_data.DEFAULT_ADMIN_USERNAME)).one()
    user.password_hash = None
    session.commit()
    session.close()


def test_nothing_is_requested_of_the_idp_by_default(sso_client: TestClient, gateway: FakeGateway) -> None:
    """⚠ Not requested by default (ADR-0039). Works as before even with an IdP that has no reserved values."""
    _start_link(sso_client, _sign_in(sso_client))

    assert gateway.sent[0].acr_values == ()


@pytest.mark.usefixtures("required_acr")
def test_the_requested_strength_is_sent_on_the_link_round_trip(
    sso_client: TestClient,
    gateway: FakeGateway,
) -> None:
    gateway.acr = "urn:assay:ac:mfa"
    headers = _sign_in(sso_client)

    assert _callback(sso_client, _start_link(sso_client, headers)) == "/security?sso_link=linked"
    assert gateway.sent[0].acr_values == ("urn:assay:ac:mfa",)


@pytest.mark.usefixtures("required_acr")
def test_a_weak_round_trip_does_not_become_a_new_entrance(
    sso_client: TestClient,
    gateway: FakeGateway,
) -> None:
    """⚠ **Linking also verifies the strength** (ADR-0039).

    If this were let through, **a round trip that passed with weak authentication becomes a new entry point as is.**
    Verifying only on the login side means nothing while the operation that adds entry points stays loose.
    """
    gateway.acr = "urn:assay:ac:single"
    headers = _sign_in(sso_client)

    assert _callback(sso_client, _start_link(sso_client, headers)) == ("/security?sso_link_error=sso_acr_not_satisfied")
    assert sso_client.get("/api/auth/sso/link", headers=headers).json()["linked"] is False


@pytest.mark.usefixtures("required_acr")
def test_an_absent_acr_does_not_become_a_new_entrance_either(
    sso_client: TestClient,
    gateway: FakeGateway,
) -> None:
    """Reading what does not come back as "satisfied" would mean the requirement is only sent."""
    headers = _sign_in(sso_client)

    assert _callback(sso_client, _start_link(sso_client, headers)) == ("/security?sso_link_error=sso_acr_not_satisfied")
