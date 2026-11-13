"""Passkey (WebAuthn) registration, listing, deletion and sign-in.

Since a real authenticator is not available, ``WebAuthnRelyingParty`` is swapped for a fake
to verify the application-side flow (issuing and consuming challenges, storing credentials,
issuing tokens). Signature verification itself is the library's job.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from bounded_contexts.account_security.domain.exceptions import (
    PasskeyVerificationError,
)
from bounded_contexts.account_security.domain.services.webauthn_relying_party import (
    PublicKeyOptions,
    VerifiedAssertion,
    VerifiedRegistration,
)
from bounded_contexts.account_security.presentation.dependencies import (
    build_relying_party,
)


@dataclass
class FakeRelyingParty:
    """A fake RP that fixes the challenge and trusts the contents of ``credential`` as is."""

    challenge: str = "Y2hhbGxlbmdl"
    accepted_challenges: list[str] = field(default_factory=list)

    def create_registration_options(
        self,
        *,
        user_id: int,
        user_name: str,
        display_name: str,
        exclude_credential_ids: Sequence[str] = (),
    ) -> PublicKeyOptions:
        return PublicKeyOptions(
            public_key={
                "challenge": self.challenge,
                "user": {"name": user_name, "displayName": display_name},
                "excludeCredentials": list(exclude_credential_ids),
            },
            challenge=self.challenge,
        )

    def verify_registration(self, *, credential: Mapping[str, Any], expected_challenge: str) -> VerifiedRegistration:
        self.accepted_challenges.append(expected_challenge)
        if credential.get("id") == "reject":
            raise PasskeyVerificationError
        return VerifiedRegistration(
            credential_id=str(credential["id"]),
            public_key="cHVibGljLWtleQ",
            sign_count=1,
            attestation_format="none",
            aaguid="00000000-0000-0000-0000-000000000000",
            backup_eligible=True,
            backup_state=False,
        )

    def create_authentication_options(self, *, allow_credential_ids: Sequence[str] = ()) -> PublicKeyOptions:
        return PublicKeyOptions(public_key={"challenge": self.challenge}, challenge=self.challenge)

    def verify_authentication(
        self,
        *,
        credential: Mapping[str, Any],
        expected_challenge: str,
        stored_public_key: str,
        stored_sign_count: int,
    ) -> VerifiedAssertion:
        if credential.get("id") == "reject":
            raise PasskeyVerificationError
        return VerifiedAssertion(credential_id=str(credential["id"]), sign_count=stored_sign_count + 1)

    def extract_credential_id(self, credential: Mapping[str, Any]) -> str | None:
        value = credential.get("id")
        return value if isinstance(value, str) else None


@pytest.fixture
def relying_party(app: FastAPI) -> Iterator[FakeRelyingParty]:
    fake = FakeRelyingParty()
    app.dependency_overrides[build_relying_party] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def _register(
    client: TestClient,
    headers: dict[str, str],
    credential_id: str = "credential-1",
    **extra: object,
) -> httpx2.Response:
    challenge = client.post("/api/account/security/passkeys/registration", headers=headers)
    assert challenge.status_code == 200, challenge.text
    return client.post(
        "/api/account/security/passkeys",
        headers=headers,
        json={
            "challenge_id": challenge.json()["challenge_id"],
            "credential": {"id": credential_id, "response": {"transports": ["usb"]}},
            **extra,
        },
    )


def test_passkey_list_requires_authentication(client: TestClient, relying_party: FakeRelyingParty) -> None:
    client.cookies.clear()
    assert client.get("/api/account/security/passkeys").status_code == 401


def test_real_relying_party_produces_browser_ready_options(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Without a fake in between, real WebAuthn options are built from the settings."""
    response = client.post("/api/account/security/passkeys/registration", headers=admin_headers)
    assert response.status_code == 200, response.text
    public_key = response.json()["public_key"]
    assert public_key["rp"]["id"] == "localhost"
    assert public_key["user"]["name"] == "admin@example.com"
    assert public_key["challenge"]
    assert public_key["pubKeyCredParams"]

    login_options = client.post("/api/auth/passkey/challenge").json()["public_key"]
    # Sign-in does not specify credentials (no need to enter an email address)
    assert login_options["allowCredentials"] == []


def test_relying_party_options_use_the_normalized_settings(
    client: TestClient, admin_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stray whitespace, uppercase and default ports in the settings are not put in the issued options.

    Passing them through makes the browser's ``rp.id`` check fail, bringing back the same symptom:
    verification passes but registration still fails.
    """
    monkeypatch.setenv("WEBAUTHN_RP_ID", " Example.COM ")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", " HTTPS://Example.com:443 ")

    response = client.post("/api/account/security/passkeys/registration", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["public_key"]["rp"]["id"] == "example.com"


def test_misconfigured_relying_party_refuses_to_issue_a_challenge(
    client: TestClient, admin_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the RP ID does not match the origin, return an error without issuing a challenge.

    Issuing one would make the browser reject it with ``SecurityError``, and the screen would show
    only an unexplained failure. Return a code that identifies a configuration error so it can be isolated.
    """
    monkeypatch.setenv("WEBAUTHN_RP_ID", "rewardpointsweb")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "https://rewardpointsweb.com")

    response = client.post("/api/account/security/passkeys/registration", headers=admin_headers)
    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "invalid_webauthn_rp_id"

    # Same for sign-in (do not hand out unusable credentials)
    assert client.post("/api/auth/passkey/challenge").status_code == 500


def test_registration_stores_the_credential(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    response = _register(client, admin_headers, name="Yubikey")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Yubikey"
    assert body["transports"] == ["usb"]

    listed = client.get("/api/account/security/passkeys", headers=admin_headers).json()
    assert [item["name"] for item in listed] == ["Yubikey"]


def test_registration_challenge_is_single_use(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    challenge = client.post("/api/account/security/passkeys/registration", headers=admin_headers).json()
    payload = {
        "challenge_id": challenge["challenge_id"],
        "credential": {"id": "credential-1", "response": {}},
    }
    assert client.post("/api/account/security/passkeys", headers=admin_headers, json=payload).status_code == 201

    replay = client.post("/api/account/security/passkeys", headers=admin_headers, json=payload)
    assert replay.status_code == 400
    assert replay.json()["detail"]["error"] == "challenge_not_found"


def test_registration_excludes_already_registered_credentials(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    _register(client, admin_headers, "credential-1")
    challenge = client.post("/api/account/security/passkeys/registration", headers=admin_headers).json()
    assert challenge["public_key"]["excludeCredentials"] == ["credential-1"]


def test_registration_rejects_another_users_challenge(
    *, client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty, db_session: Session
) -> None:
    """Registration fails with a challenge issued to someone else.

    Without this check, B holding A's challenge_id could save "a credential issued for A"
    to B's account and from then on sign in as B with it.
    """
    from bounded_contexts.account_security.infrastructure.account_security_models import (
        WebAuthnChallengeRecord,
    )

    challenge = client.post("/api/account/security/passkeys/registration", headers=admin_headers).json()

    # After issuing, rewrite only the owner to another user (holding someone else's challenge)
    record = db_session.get(WebAuthnChallengeRecord, challenge["challenge_id"])
    assert record is not None
    record.user_id = None
    db_session.commit()

    response = client.post(
        "/api/account/security/passkeys",
        headers=admin_headers,
        json={
            "challenge_id": challenge["challenge_id"],
            "credential": {"id": "credential-1", "response": {}},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "challenge_not_found"
    assert client.get("/api/account/security/passkeys", headers=admin_headers).json() == []


def test_unnamed_passkey_gets_a_fallback_name(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    response = _register(client, admin_headers, "abcdefghij")
    assert response.json()["name"] == "passkey-abcdefgh"


def test_delete_removes_the_passkey(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    passkey_id = _register(client, admin_headers).json()["id"]
    assert client.delete(f"/api/account/security/passkeys/{passkey_id}", headers=admin_headers).status_code == 204
    assert client.get("/api/account/security/passkeys", headers=admin_headers).json() == []


def test_delete_unknown_passkey_returns_not_found(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    response = client.delete("/api/account/security/passkeys/9999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "passkey_not_found"


def test_login_with_a_registered_passkey(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    _register(client, admin_headers)
    client.cookies.clear()

    challenge = client.post("/api/auth/passkey/challenge")
    assert challenge.status_code == 200
    response = client.post(
        "/api/auth/passkey/login",
        json={
            "challenge_id": challenge.json()["challenge_id"],
            "credential": {"id": "credential-1", "response": {}},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


def test_login_with_an_unknown_credential_is_rejected(client: TestClient, relying_party: FakeRelyingParty) -> None:
    challenge = client.post("/api/auth/passkey/challenge").json()
    response = client.post(
        "/api/auth/passkey/login",
        json={
            "challenge_id": challenge["challenge_id"],
            "credential": {"id": "never-registered", "response": {}},
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "passkey_verification_failed"


def test_failed_verification_is_reported_as_unauthorized(
    client: TestClient, admin_headers: dict[str, str], relying_party: FakeRelyingParty
) -> None:
    response = _register(client, admin_headers, "reject")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "passkey_verification_failed"
    # A credential that failed verification is not saved
    assert client.get("/api/account/security/passkeys", headers=admin_headers).json() == []
