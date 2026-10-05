"""表示端末（サイネージ）のペアリングと、表示アカウントの立場（ADR-0047）。

- 承認できるのは運用管理者（``display:approve``）だけ。admin・親・子は断られる
- 確認コードだけでは受け取れない。受け取りは端末の秘密で、1 度だけ
- 表示アカウントは家族の全部の子の台帳を見るだけで、変えられない
- 外すと（運用管理者・家族の親のどちらからでも）次の取り直しで断られる
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from bounded_contexts.display_devices.infrastructure.display_devices_models import DisplayCredentialRecord
from shared.kernel.timestamps import utcnow
from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
)


@dataclass(frozen=True, kw_only=True)
class Household:
    owner: Account
    family_id: int
    ledgers: tuple[Ledger, ...]


@dataclass(frozen=True, kw_only=True)
class PairedDisplay:
    account_id: int
    membership_id: int
    credential: str

    def headers(self, client: TestClient) -> dict[str, str]:
        response = client.post("/api/display/session", json={"device_credential": self.credential})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def operator(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="ops", role="operator", display_name="運用管理者")


@pytest.fixture
def household(client: TestClient, admin_headers: dict[str, str]) -> Household:
    owner = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    family_id = create_family(client, owner.headers, name="ほその家")
    ledgers = tuple(
        Ledger(
            family_id=family_id,
            ledger_id=int(str(add_child(client, owner.headers, family_id, display_name=name)["ledger_id"])),
        )
        for name in ("たろう", "はなこ")
    )
    ledgers[0].record(client, owner.headers, amount=30, reason="おてつだい", key="k1")
    return Household(owner=owner, family_id=family_id, ledgers=ledgers)


def _start(client: TestClient) -> dict[str, object]:
    response = client.post("/api/display/pairings")
    assert response.status_code == 201, response.text
    started: dict[str, object] = response.json()
    return started


def _approve(
    client: TestClient, approver: Account, *, user_code: object, family_id: int, name: str = "リビング"
) -> dict[str, object]:
    response = client.post(
        "/api/display/pairings/approve",
        headers=approver.headers,
        json={"user_code": user_code, "family_id": family_id, "name": name},
    )
    assert response.status_code == 201, response.text
    approved: dict[str, object] = response.json()
    return approved


def _claim(client: TestClient, device_code: object) -> tuple[int, dict[str, object]]:
    response = client.post("/api/display/pairings/claim", json={"device_code": device_code})
    body: dict[str, object] = response.json()
    return response.status_code, body


def _pair(client: TestClient, operator: Account, household: Household) -> PairedDisplay:
    started = _start(client)
    approved = _approve(client, operator, user_code=started["user_code"], family_id=household.family_id)
    status_code, claimed = _claim(client, started["device_code"])
    assert status_code == 200, claimed
    family = client.get(f"/api/families/{household.family_id}", headers=household.owner.headers).json()
    membership_id = next(m["id"] for m in family["memberships"] if m["role"] == "display")
    return PairedDisplay(
        account_id=int(str(approved["account_id"])),
        membership_id=membership_id,
        credential=str(claimed["device_credential"]),
    )


# --- ペアリング ----------------------------------------------------------------


def test_a_display_is_paired_by_the_operator_and_claims_its_credential_once(
    client: TestClient, operator: Account, household: Household
) -> None:
    started = _start(client)
    assert str(started["user_code"])[4] == "-"
    assert started["expires_in"] == 600
    assert started["interval"] == 5

    status_code, body = _claim(client, started["device_code"])
    assert (status_code, body["detail"]) == (400, {"error": "authorization_pending"})

    approved = _approve(client, operator, user_code=started["user_code"], family_id=household.family_id)
    assert approved["family_name"] == "ほその家"
    assert approved["name"] == "リビング"

    status_code, body = _claim(client, started["device_code"])
    assert status_code == 200
    assert body["device_credential"]

    # 受け取りは 1 度だけ
    status_code, body = _claim(client, started["device_code"])
    assert (status_code, body["detail"]) == (400, {"error": "expired_token"})


def test_the_user_code_alone_cannot_claim(client: TestClient, operator: Account, household: Household) -> None:
    started = _start(client)
    _approve(client, operator, user_code=started["user_code"], family_id=household.family_id)

    status_code, body = _claim(client, started["user_code"])
    assert (status_code, body["detail"]) == (400, {"error": "expired_token"})


def test_the_user_code_is_typed_loosely(client: TestClient, operator: Account, household: Household) -> None:
    """区切りなし・小文字でも通る（人が打つので）。"""
    started = _start(client)
    loose = str(started["user_code"]).replace("-", "").lower()
    _approve(client, operator, user_code=loose, family_id=household.family_id)


def test_unknown_and_reused_codes_are_refused(client: TestClient, operator: Account, household: Household) -> None:
    started = _start(client)
    _approve(client, operator, user_code=started["user_code"], family_id=household.family_id)

    for code in (started["user_code"], "AAAA-AAAA", "0000-0000"):
        response = client.post(
            "/api/display/pairings/approve",
            headers=operator.headers,
            json={"user_code": code, "family_id": household.family_id, "name": "もう 1 台"},
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"] == {"error": "pairing_not_found"}
    # 断ったときは表示アカウントを作らない
    devices = client.get("/api/display/devices", headers=operator.headers).json()
    assert len(devices) == 1


def test_an_expired_code_cannot_be_approved_or_claimed(
    *, client: TestClient, operator: Account, household: Household, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _start(client)
    later = utcnow() + timedelta(minutes=11)
    monkeypatch.setattr("bounded_contexts.display_devices.application.use_cases.pair_display.utcnow", lambda: later)

    response = client.post(
        "/api/display/pairings/approve",
        headers=operator.headers,
        json={"user_code": started["user_code"], "family_id": household.family_id, "name": "リビング"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == {"error": "pairing_expired"}
    status_code, body = _claim(client, started["device_code"])
    assert (status_code, body["detail"]) == (400, {"error": "expired_token"})


@pytest.mark.parametrize("role", ["admin", "member", "manager"])
def test_only_the_operator_approves(
    *, client: TestClient, admin_headers: dict[str, str], household: Household, role: str
) -> None:
    someone = create_account(client, admin_headers, username=f"someone-{role}", role=role)
    started = _start(client)

    response = client.post(
        "/api/display/pairings/approve",
        headers=someone.headers,
        json={"user_code": started["user_code"], "family_id": household.family_id, "name": "リビング"},
    )
    assert response.status_code == 403
    status_code, body = _claim(client, started["device_code"])
    assert (status_code, body["detail"]) == (400, {"error": "authorization_pending"})


def test_the_owner_of_the_family_cannot_approve_either(client: TestClient, household: Household) -> None:
    started = _start(client)
    response = client.post(
        "/api/display/pairings/approve",
        headers=household.owner.headers,
        json={"user_code": started["user_code"], "family_id": household.family_id, "name": "リビング"},
    )
    assert response.status_code == 403


def test_the_admin_has_no_display_approve_and_the_operator_role_exists(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    roles = {
        role["name"]: set(role["permissions"]) for role in client.get("/api/admin/roles", headers=admin_headers).json()
    }
    assert roles["operator"] == {"dashboard:view", "gui:view", "display:approve"}
    assert "display:approve" not in roles["admin"]


# --- 表示アカウントの立場 -------------------------------------------------------


def test_a_display_sees_every_child_but_changes_nothing(
    client: TestClient, operator: Account, household: Household
) -> None:
    display = _pair(client, operator, household)
    headers = display.headers(client)

    family = client.get(f"/api/families/{household.family_id}", headers=headers).json()
    assert family["my_role"] == "display"
    balances = {m["display_name"]: m["balance"] for m in family["memberships"] if m["role"] == "child"}
    assert balances == {"たろう": 30, "はなこ": 0}
    for ledger in household.ledgers:
        assert client.get(ledger.path(), headers=headers).status_code == 200

    denied = client.post(
        f"{household.ledgers[0].path()}/transactions",
        headers=headers,
        json={"amount": 5, "reason": "かってに", "idempotency_key": "d1"},
    )
    assert denied.status_code == 403
    assert client.get(household.ledgers[0].path(), headers=household.owner.headers).json()["balance"] == 30
    for method, path in (
        ("post", f"/api/families/{household.family_id}/memberships"),
        ("post", f"/api/families/{household.family_id}/invitations"),
        ("patch", f"/api/families/{household.family_id}"),
    ):
        assert (
            client.request(
                method, path, headers=headers, json={"display_name": "x", "role": "parent", "name": "x"}
            ).status_code
            == 403
        )


def test_a_display_cannot_reach_another_family(
    *, client: TestClient, admin_headers: dict[str, str], operator: Account, household: Household
) -> None:
    other = create_account(client, admin_headers, username="neighbor", role="member")
    other_family = create_family(client, other.headers, name="となりの家")
    other_ledger = add_child(client, other.headers, other_family, display_name="じろう")["ledger_id"]
    headers = _pair(client, operator, household).headers(client)

    assert client.get(f"/api/families/{other_family}", headers=headers).status_code == 403
    assert client.get(f"/api/families/{other_family}/ledgers/{other_ledger}", headers=headers).status_code == 403


def test_a_display_is_listed_apart_from_people(client: TestClient, operator: Account, household: Household) -> None:
    _pair(client, operator, household)

    listed = client.get("/api/families", headers=household.owner.headers).json()
    # 親 1・子 2。表示端末は数えない
    assert listed[0]["member_count"] == 3
    family = client.get(f"/api/families/{household.family_id}", headers=household.owner.headers).json()
    roles = [m["role"] for m in family["memberships"]]
    assert roles == ["owner", "child", "child", "display"]
    display = family["memberships"][-1]
    assert display["display_name"] == "リビング"
    assert display["ledger_id"] is None
    assert display["can_remove"] is True


def test_a_display_cannot_change_credentials_profile_or_leave(
    client: TestClient, operator: Account, household: Household
) -> None:
    headers = _pair(client, operator, household).headers(client)

    profile = client.put("/api/auth/me", headers=headers, json={"email": "me@example.com"})
    assert profile.status_code == 403
    assert profile.json()["detail"] == {"error": "display_device_not_allowed"}
    totp = client.post("/api/account/security/two-factor/enrollment", headers=headers)
    assert totp.status_code == 403
    passkey = client.post("/api/account/security/passkeys/registration", headers=headers)
    assert passkey.status_code == 403
    link = client.post("/api/auth/sso/link/start", headers=headers)
    assert link.status_code == 403
    leave = client.post(f"/api/families/{household.family_id}/leave", headers=headers)
    assert leave.status_code == 403


def test_a_display_has_no_password_and_shows_up_as_a_device(
    *, client: TestClient, admin_headers: dict[str, str], operator: Account, household: Household
) -> None:
    display = _pair(client, operator, household)
    users = {u["id"]: u for u in client.get("/api/admin/users", headers=admin_headers).json()}
    entrances = users[display.account_id]["entrances"]
    assert entrances == {
        "password": False,
        "totp": False,
        "passkeys": 0,
        "identity_providers": [],
        "display_device": True,
    }
    assert users[display.account_id]["roles"] == ["display"]

    login = client.post(
        "/api/auth/login", json={"username": users[display.account_id]["username"], "password": "x" * 8}
    )
    assert login.status_code == 401


def test_the_family_archive_leaves_displays_out(client: TestClient, operator: Account, household: Household) -> None:
    _pair(client, operator, household)
    archive = client.get(f"/api/families/{household.family_id}/export", headers=household.owner.headers).json()
    assert all(member["role"] != "display" for member in archive["members"])


# --- 外す -----------------------------------------------------------------------


def test_the_operator_lists_and_removes_a_display(client: TestClient, operator: Account, household: Household) -> None:
    display = _pair(client, operator, household)
    display.headers(client)

    devices = client.get("/api/display/devices", headers=operator.headers).json()
    assert [(d["name"], d["family_name"]) for d in devices] == [("リビング", "ほその家")]
    assert devices[0]["last_used_at"] is not None
    families = client.get("/api/display/families", headers=operator.headers).json()
    assert families == [{"id": household.family_id, "name": "ほその家"}]

    response = client.delete(f"/api/display/devices/{display.account_id}", headers=operator.headers)
    assert response.status_code == 204
    again = client.post("/api/display/session", json={"device_credential": display.credential})
    assert again.status_code == 401
    assert client.get("/api/display/devices", headers=operator.headers).json() == []
    family = client.get(f"/api/families/{household.family_id}", headers=household.owner.headers).json()
    assert all(m["role"] != "display" for m in family["memberships"])


def test_a_parent_removes_a_display_from_the_family_page(
    *, client: TestClient, admin_headers: dict[str, str], operator: Account, household: Household
) -> None:
    parent = create_account(client, admin_headers, username="mom", role="member")
    invitation = issue_invitation(client, household.owner.headers, household.family_id, role="parent")
    joined = client.post("/api/families/invitations/accept", headers=parent.headers, json={"code": invitation["code"]})
    assert joined.status_code == 200, joined.text
    display = _pair(client, operator, household)

    response = client.delete(
        f"/api/families/{household.family_id}/memberships/{display.membership_id}", headers=parent.headers
    )
    assert response.status_code == 204, response.text
    assert client.post("/api/display/session", json={"device_credential": display.credential}).status_code == 401
    assert client.get("/api/display/devices", headers=operator.headers).json() == []


def test_an_unused_credential_expires_and_the_display_is_removed(
    *, client: TestClient, operator: Account, household: Household, db_session: Session
) -> None:
    display = _pair(client, operator, household)
    db_session.execute(
        update(DisplayCredentialRecord)
        .where(DisplayCredentialRecord.account_id == display.account_id)
        .values(last_used_at=utcnow() - timedelta(days=91))
    )
    db_session.commit()

    response = client.post("/api/display/session", json={"device_credential": display.credential})
    assert response.status_code == 401
    assert response.json()["detail"] == {"error": "device_credential_expired"}
    assert client.get("/api/display/devices", headers=operator.headers).json() == []


def test_an_unknown_credential_is_refused(client: TestClient) -> None:
    response = client.post("/api/display/session", json={"device_credential": "not-a-credential"})
    assert response.status_code == 401
    assert response.json()["detail"] == {"error": "invalid_device_credential"}
