"""家族を共有単位とする認可（ADR-0009）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
)


@pytest.fixture
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="manager", display_name="おとうさん")


@pytest.fixture
def other_parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="stranger", role="manager")


def test_family_creator_becomes_owner(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)

    response = client.get(f"/api/families/{family_id}", headers=parent.headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["my_role"] == "owner"
    assert [m["display_name"] for m in data["memberships"]] == ["おとうさん"]

    listed = client.get("/api/families", headers=parent.headers).json()
    assert [f["id"] for f in listed] == [family_id]
    assert listed[0]["member_count"] == 1


def test_child_gets_a_ledger_on_creation(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    assert child["role"] == "child"
    assert child["is_linked"] is False
    assert child["ledger_id"] is not None
    assert child["balance"] == 0


def test_other_family_is_not_visible(client: TestClient, parent: Account, other_parent: Account) -> None:
    family_id = create_family(client, parent.headers)

    denied = client.get(f"/api/families/{family_id}", headers=other_parent.headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "family_access_denied"
    assert client.get("/api/families", headers=other_parent.headers).json() == []


def test_siblings_cannot_see_each_other(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    older = add_child(client, parent.headers, family_id, display_name="あに")
    younger = add_child(client, parent.headers, family_id, display_name="おとうと")

    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(older["id"]))
    )
    signup = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "ani", "password": "ani-pass-123"},
    )
    assert signup.status_code == 201, signup.text
    child_headers = {
        "Authorization": "Bearer "
        + client.post("/api/auth/login", json={"username": "ani", "password": "ani-pass-123"}).json()["access_token"]
    }

    detail = client.get(f"/api/families/{family_id}", headers=child_headers).json()
    by_name = {m["display_name"]: m for m in detail["memberships"]}
    # 同じ家族に誰がいるかは見えてよいが、兄弟の残高・台帳は見えない
    assert by_name["あに"]["ledger_id"] is not None
    assert by_name["おとうと"]["ledger_id"] is None
    assert by_name["おとうと"]["balance"] is None

    younger_ledger = younger["ledger_id"]
    denied = client.get(f"/api/families/{family_id}/ledgers/{younger_ledger}", headers=child_headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "family_access_denied"


def test_child_cannot_modify_own_ledger(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    child_headers = {
        "Authorization": "Bearer "
        + client.post("/api/auth/login", json={"username": "taro", "password": "taro-pass-123"}).json()["access_token"]
    }

    ledger_id = child["ledger_id"]
    ledger = client.get(f"/api/families/{family_id}/ledgers/{ledger_id}", headers=child_headers)
    assert ledger.status_code == 200
    assert ledger.json()["can_modify"] is False

    # scope（member ロールに point:manage が無い）で止まる
    denied = client.post(
        f"/api/families/{family_id}/ledgers/{ledger_id}/transactions",
        headers=child_headers,
        json={"amount": 10, "reason": "self service", "idempotency_key": "k1"},
    )
    assert denied.status_code == 403


def test_invited_parent_can_manage_every_child(client: TestClient, parent: Account, other_parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")

    accepted = client.post(
        "/api/families/invitations/accept",
        headers=other_parent.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "parent"

    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    added = ledger.record(client, other_parent.headers, amount=30, reason="おてつだい", key="k1")
    assert added["granted_by"] == "おかあさん"


def test_parent_cannot_administer_family(client: TestClient, parent: Account, other_parent: Account) -> None:
    """家族の管理（招待・除名）は owner のみ。子の作成と記録は parent もできる。"""
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")
    client.post(
        "/api/families/invitations/accept",
        headers=other_parent.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )

    removal = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=other_parent.headers)
    assert removal.status_code == 403
    assert removal.json()["detail"]["error"] == "family_access_denied"

    issuing = client.post(
        f"/api/families/{family_id}/invitations",
        headers=other_parent.headers,
        json={"role": "child", "target_membership_id": child["id"]},
    )
    assert issuing.status_code == 403
    assert client.get(f"/api/families/{family_id}/invitations", headers=other_parent.headers).status_code == 403

    # 子の作成はできる
    assert (
        client.post(
            f"/api/families/{family_id}/memberships",
            headers=other_parent.headers,
            json={"display_name": "はなこ"},
        ).status_code
        == 201
    )


def test_membership_with_records_cannot_be_removed(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")

    response = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=parent.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "ledger_not_empty"

    # 記録が無ければ外せる
    empty = add_child(client, parent.headers, family_id, display_name="はなこ")
    assert (
        client.delete(f"/api/families/{family_id}/memberships/{empty['id']}", headers=parent.headers).status_code == 204
    )


def test_owner_account_cannot_be_deleted(client: TestClient, admin_headers: dict[str, str], parent: Account) -> None:
    create_family(client, parent.headers)

    response = client.delete(f"/api/admin/users/{parent.user_id}", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "user_still_owns_families"
