"""The SSO sign-in round trip (ADR-0029).

Communication with the IdP is stopped by swapping the gateway. What this checks is **how this app
puts it together** -- the stored-state round trip, binding to the browser, the exchange ticket, and creating
an account for a first-time visitor "only when it can be created" (ADR-0041).
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
    """Stand-in for the IdP. Records the requests it receives and returns fixed claims."""

    claims: dict[str, Any]
    seen: list[CodeExchange] = field(default_factory=list)
    sent: list[AuthorizationRequest] = field(default_factory=list)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        self.sent.append(request)
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
    # ⚠ Linking by email is not the default (ADR-0033). Enabled here because we want to see the round trip itself.
    monkeypatch.setenv("OIDC_LINK_BY_EMAIL", "true")


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway(claims={"email": EMAIL, "email_verified": True, "name": "親"})


@pytest.fixture
def required_acr(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ **If you request it, verify it** (ADR-0039). Switch to the mode that requests it."""
    monkeypatch.setenv("OIDC_ACR_VALUES", '["urn:assay:ac:mfa"]')


@pytest.fixture
def sso_client(
    app: FastAPI,
    gateway: FakeGateway,
    sso_settings: None,
) -> Iterator[TestClient]:
    app.dependency_overrides[dependencies.oidc_gateway] = lambda: gateway
    # The return from the IdP is a chain of 303s; following it would hide the Location to check
    with TestClient(app, follow_redirects=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def parent(engine: sa.Engine) -> int:
    """An existing user with an email address (the target SSO links to)."""
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
    """Proceed up to sending the user out, and return the stored ``state``."""
    response = client.get("/api/auth/sso/login", params={"redirect_to": redirect_to})
    assert response.status_code == 303, response.text
    assert SSO_BINDING_COOKIE in response.cookies
    state = parse_qs(urlparse(response.headers["location"]).query)["state"]
    return str(state[0])


def _callback(client: TestClient, state: str) -> str:
    """Proceed through the return, and return the exchange ticket handed to the SPA."""
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
    # The issued token belongs to that person
    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == parent
    # The PKCE verifier and nonce passed are the stored ones
    assert gateway.seen[0].code_verifier
    assert gateway.seen[0].nonce


def test_the_second_sign_in_goes_through_the_stored_link(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    """Once linked, sign-in works even if the email address changes at the IdP."""
    sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))})

    gateway.claims = {"email": "renamed@example.com", "email_verified": True, "name": "親"}
    body = sso_client.post(
        "/api/auth/sso/token",
        json={"ticket": _callback(sso_client, _start(sso_client))},
    ).json()

    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == parent


def test_a_first_visit_creates_the_account(sso_client: TestClient, gateway: FakeGateway, engine: sa.Engine) -> None:
    """Whoever comes back from assay is someone assigned to the app. On a first visit, create an account to welcome them (ADR-0041).

    ⚠ The created account matches the admin console default: **a parent (``member``) with no family**, and **no password**.
    """
    before = _user_count(engine)
    gateway.claims = {
        "email": "new@example.com",
        "email_verified": True,
        "name": "新しい親",
        "preferred_username": "Newcomer",
    }

    body = sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))}).json()

    assert _user_count(engine) == before + 1
    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    user = _user(engine, me["user_id"])
    assert (user.username, user.email, user.display_name) == ("newcomer", "new@example.com", "新しい親")
    assert user.password_hash is None
    assert [role.name for role in user.roles] == ["member"]
    assert body["must_change_password"] is False


def test_the_created_account_is_found_by_its_link_next_time(
    sso_client: TestClient, gateway: FakeGateway, engine: sa.Engine
) -> None:
    """The second time is resolved by ``(issuer, subject)``. ⚠ Do not create a second account."""
    gateway.claims = {
        "email": "new@example.com",
        "email_verified": True,
        "name": "新しい親",
        "preferred_username": "newcomer",
    }
    first = sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))}).json()
    before = _user_count(engine)

    second = sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))}).json()

    assert _user_count(engine) == before
    headers = [{"Authorization": f"Bearer {body['access_token']}"} for body in (first, second)]
    assert (
        sso_client.get("/api/auth/me", headers=headers[0]).json()["user_id"]
        == (sso_client.get("/api/auth/me", headers=headers[1]).json()["user_id"])
    )


def test_a_taken_username_is_refused_instead_of_renamed(
    sso_client: TestClient, gateway: FakeGateway, engine: sa.Engine
) -> None:
    """⚠ **On a collision, refuse instead of creating** (ADR-0041). Silently appending a number would give an identifier the person does not know."""
    _other_user(engine, username="newcomer", email="someone-else@example.com")
    before = _user_count(engine)
    gateway.claims = {"email": "new@example.com", "email_verified": True, "preferred_username": "NewComer"}

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_username_unavailable"
    assert _user_count(engine) == before


@pytest.mark.parametrize("claims", [{"email": "new@example.com"}, {"preferred_username": "日本語の名前"}])
def test_an_unusable_username_is_refused(
    *, sso_client: TestClient, gateway: FakeGateway, engine: sa.Engine, claims: dict[str, Any]
) -> None:
    """``preferred_username`` is missing, or does not fit the identifier rules. Neither creates an account."""
    before = _user_count(engine)
    gateway.claims = claims

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_username_unavailable"
    assert _user_count(engine) == before


def test_an_address_an_unlinked_account_already_has_is_refused(
    *,
    monkeypatch: pytest.MonkeyPatch,
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
    engine: sa.Engine,
) -> None:
    """⚠ **Refused on purpose** (ADR-0041). Creating one would give the same person two accounts.

    Linking by email is closed by default (ADR-0033). The person signs in to that account and links it (ADR-0036).
    """
    monkeypatch.setenv("OIDC_LINK_BY_EMAIL", "false")
    before = _user_count(engine)
    gateway.claims = {"email": EMAIL, "email_verified": True, "preferred_username": "someone"}

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_account_not_linked"
    assert _user_count(engine) == before


def test_an_address_an_invited_account_holds_as_its_username_is_refused(
    *,
    monkeypatch: pytest.MonkeyPatch,
    sso_client: TestClient,
    gateway: FakeGateway,
    engine: sa.Engine,
) -> None:
    """⚠ Accounts created by invitation have no ``email`` (ADR-0011). If the identifier is that address, it is the same person.

    Missing this creates a second account and drops the person out of their family (happened in production on 2026-10-05).
    """
    monkeypatch.setenv("OIDC_LINK_BY_EMAIL", "false")
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(username=EMAIL, email=None, display_name="親", password_hash=generate_password_hash("password")))
    session.commit()
    session.close()
    before = _user_count(engine)
    gateway.claims = {"email": EMAIL, "email_verified": True, "preferred_username": "someone"}

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
    """Even if tricked into following an authorization request the attacker started, the victim does not sign in as the attacker."""
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
    """The IdP's error code goes straight into the screen URL. Only let through values of a known shape."""
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


def _user(engine: sa.Engine, user_id: int) -> User:
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = session.get(User, user_id)
    assert user is not None
    session.close()
    return user


def _other_user(engine: sa.Engine, *, username: str, email: str) -> None:
    """The one the copy update collides with (``users.email`` is unique)."""
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(username=username, email=email, display_name=username, password_hash=None))
    session.commit()
    session.close()


def _user_count(engine: sa.Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(sa.select(sa.func.count()).select_from(User.__table__)).scalar_one())


def test_the_profile_copy_follows_the_idp(
    *,
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
    engine: sa.Engine,
) -> None:
    """⚠ **The copy treats the IdP as the source of truth** (ADR-0038).

    Without rewriting it, a rename or email change over there would leave **the display here stale forever**.
    ⚠ ``username`` (the login identifier) is not touched.
    """
    sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))})
    gateway.claims = {"email": "renamed@example.com", "email_verified": True, "name": "改名した親"}

    _callback(sso_client, _start(sso_client))

    user = _user(engine, parent)
    assert (user.email, user.display_name, user.username) == ("renamed@example.com", "改名した親", "parent")


def test_a_name_another_user_already_has_is_not_written(
    *,
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
    engine: sa.Engine,
) -> None:
    """⚠ **Do not write a colliding value.** Updating the copy must not break sign-in."""
    sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))})
    _other_user(engine, username="sibling", email="taken@example.com")
    gateway.claims = {"email": "taken@example.com", "email_verified": True, "name": "親"}

    _callback(sso_client, _start(sso_client))

    assert _user(engine, parent).email == EMAIL


def test_a_linked_user_signs_in_without_an_email_claim(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    """The key is ``(issuer, subject)``. ⚠ **Even without an email, a linked account can sign in** (ADR-0038)."""
    sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))})
    gateway.claims = {"name": "親"}

    body = sso_client.post(
        "/api/auth/sso/token",
        json={"ticket": _callback(sso_client, _start(sso_client))},
    ).json()

    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == parent


def test_a_first_visit_without_an_email_claim_still_creates_the_account(
    sso_client: TestClient, gateway: FakeGateway, engine: sa.Engine
) -> None:
    """The email address is not the key (ADR-0038). An account can be created without one -- what is needed is ``username``."""
    gateway.claims = {"name": "親", "preferred_username": "no-mail"}

    body = sso_client.post("/api/auth/sso/token", json={"ticket": _callback(sso_client, _start(sso_client))}).json()

    me = sso_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert (_user(engine, me["user_id"]).username, _user(engine, me["user_id"]).email) == ("no-mail", None)


def test_nothing_is_requested_of_the_idp_by_default(sso_client: TestClient, gateway: FakeGateway) -> None:
    """⚠ Not requested by default (ADR-0039). IdPs without the reserved values keep working as before."""
    _start(sso_client)

    assert gateway.sent[0].acr_values == ()


@pytest.mark.usefixtures("required_acr")
def test_the_requested_strength_is_sent_and_checked(
    sso_client: TestClient,
    gateway: FakeGateway,
    parent: int,
) -> None:
    gateway.claims = {"email": EMAIL, "email_verified": True, "name": "親", "acr": "urn:assay:ac:mfa"}

    ticket = _callback(sso_client, _start(sso_client))

    assert gateway.sent[0].acr_values == ("urn:assay:ac:mfa",)
    assert sso_client.post("/api/auth/sso/token", json={"ticket": ticket}).status_code == 200


@pytest.mark.usefixtures("required_acr")
def test_a_weaker_sign_in_is_refused(sso_client: TestClient, gateway: FakeGateway, parent: int) -> None:
    """⚠ **This is the crux.** Merely sending it guarantees nothing (ADR-0039)."""
    gateway.claims = {"email": EMAIL, "email_verified": True, "acr": "urn:assay:ac:single"}

    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_acr_not_satisfied"


@pytest.mark.usefixtures("required_acr")
def test_an_absent_acr_is_refused_too(sso_client: TestClient, gateway: FakeGateway, parent: int) -> None:
    """Reading a missing value as "satisfied" would mean the request was only sent."""
    response = sso_client.get(
        "/api/auth/sso/callback",
        params={"code": "authorization-code", "state": _start(sso_client)},
    )

    assert response.headers["location"] == "/login?sso_error=sso_acr_not_satisfied"


def _start_silently(client: TestClient, redirect_to: str = "/families") -> str:
    """Start the trial run made when the login screen opens (ADR-0052), and return ``state``."""
    response = client.get("/api/auth/sso/login", params={"prompt": "none", "redirect_to": redirect_to})
    assert response.status_code == 303, response.text
    return str(parse_qs(urlparse(response.headers["location"]).query)["state"][0])


def test_a_silent_attempt_asks_the_idp_not_to_show_a_screen(sso_client: TestClient, gateway: FakeGateway) -> None:
    _start_silently(sso_client)
    assert gateway.sent[-1].silent is True
    # Not attached to an ordinary round trip
    _start(sso_client)
    assert gateway.sent[-1].silent is False


@pytest.mark.parametrize(
    "error",
    ["login_required", "consent_required", "interaction_required", "account_selection_required", "access_denied"],
)
def test_a_declined_silent_attempt_returns_to_the_login_screen_without_an_error(
    sso_client: TestClient, error: str
) -> None:
    """Not signed in at the IdP. Not a failure, so no ``sso_error``; the destination is carried back."""
    state = _start_silently(sso_client, "/families")
    back = sso_client.get("/api/auth/sso/callback", params={"error": error, "state": state})
    assert back.status_code == 303
    assert back.headers["location"] == "/login?sso_silent=declined&redirect_to=%2Ffamilies"


def test_a_declined_ordinary_attempt_is_still_an_error(sso_client: TestClient) -> None:
    """``login_required`` on a round trip started from the button still comes back as an error, as before."""
    state = _start(sso_client)
    back = sso_client.get("/api/auth/sso/callback", params={"error": "login_required", "state": state})
    assert "sso_error=login_required" in back.headers["location"]


def test_a_declined_silent_attempt_from_another_browser_is_still_an_error(sso_client: TestClient) -> None:
    """A return without the shared-secret cookie is not silently swallowed, even on a trial round trip."""
    state = _start_silently(sso_client)
    sso_client.cookies.clear()
    back = sso_client.get("/api/auth/sso/callback", params={"error": "login_required", "state": state})
    assert "sso_error=login_required" in back.headers["location"]
