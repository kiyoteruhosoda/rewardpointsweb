"""メールアドレスを持たない子アカウントでも二要素・パスキーが使えること。

TOTP も WebAuthn もメールアドレスに依存しない（ADR-0011）。既定では有効化
されていないことも併せて確かめる。
"""

from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from tests.integration.api.family_support import (
    Account,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)
from tests.integration.api.software_authenticator import SoftwareAuthenticator

# 既定の WEBAUTHN_RP_ID / WEBAUTHN_ORIGIN と揃える
RP_ID = "localhost"
ORIGIN = "http://localhost:5173"

CHILD_PASSWORD = "taro-pass-123"


@pytest.fixture
def child_headers(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    """招待コードで作った、メールアドレスを持たない子アカウント。"""
    parent: Account = create_account(client, admin_headers, username="dad", role="manager")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": CHILD_PASSWORD},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username="taro", password=CHILD_PASSWORD)


def test_two_factor_is_off_by_default(client: TestClient, child_headers: dict[str, str]) -> None:
    assert client.get("/api/auth/me", headers=child_headers).json()["email"] is None
    assert client.get("/api/account/security/two-factor", headers=child_headers).json() == {
        "enabled": False,
        "enrolling": False,
    }
    assert client.get("/api/account/security/passkeys", headers=child_headers).json() == []


def test_totp_can_be_enrolled_and_used(client: TestClient, child_headers: dict[str, str]) -> None:
    enrollment = client.post("/api/account/security/two-factor/enrollment", headers=child_headers)
    assert enrollment.status_code == 200, enrollment.text
    secret = str(enrollment.json()["secret"])
    # 発行者名にはログイン識別子を使う（メールアドレスが無くても成立する）
    assert "taro" in enrollment.json()["otpauth_uri"]

    confirmation = client.post(
        "/api/account/security/two-factor/confirmation",
        headers=child_headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert confirmation.status_code == 200, confirmation.text

    without_code = client.post("/api/auth/login", json={"username": "taro", "password": CHILD_PASSWORD})
    assert without_code.status_code == 401
    assert without_code.json()["detail"]["error"] == "totp_required"

    with_code = client.post(
        "/api/auth/login",
        json={"username": "taro", "password": CHILD_PASSWORD, "totp_code": pyotp.TOTP(secret).now()},
    )
    assert with_code.status_code == 200


def test_passkey_can_be_registered_and_used(client: TestClient, child_headers: dict[str, str]) -> None:
    authenticator = SoftwareAuthenticator(rp_id=RP_ID, origin=ORIGIN)

    challenge = client.post("/api/account/security/passkeys/registration", headers=child_headers)
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    registered = client.post(
        "/api/account/security/passkeys",
        headers=child_headers,
        json={
            "challenge_id": body["challenge_id"],
            "credential": authenticator.register(body["public_key"]["challenge"]),
            "name": "きょうしつのタブレット",
        },
    )
    assert registered.status_code == 201, registered.text

    client.cookies.clear()
    assertion = client.post("/api/auth/passkey/challenge")
    assert assertion.status_code == 200, assertion.text
    assertion_body = assertion.json()
    signed_in = client.post(
        "/api/auth/passkey/login",
        json={
            "challenge_id": assertion_body["challenge_id"],
            "credential": authenticator.authenticate(assertion_body["public_key"]["challenge"]),
        },
    )
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["access_token"]
