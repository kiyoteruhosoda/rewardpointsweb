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
    login,
)


@pytest.fixture
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


@pytest.fixture
def other_parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="stranger", role="member")


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

    # scope（guest ロールに point:manage が無い）で止まる
    denied = client.post(
        f"/api/families/{family_id}/ledgers/{ledger_id}/transactions",
        headers=child_headers,
        json={"amount": 10, "reason": "self service", "idempotency_key": "k1"},
    )
    assert denied.status_code == 403


# --- 家族を作れるのは親（member）だけ（ADR-0018） ----------------------------


def _linked_child_headers(client: TestClient, parent: Account, family_id: int, *, username: str) -> dict[str, str]:
    """アカウントの結び付いた子（guest ロール）を用意してログインする。"""
    child = add_child(client, parent.headers, family_id, display_name=username)
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": f"{username}-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username=username, password=f"{username}-pass-123")


def test_member_creates_and_manages_without_relogin(client: TestClient, parent: Account) -> None:
    """親（member）は最初から family:manage / point:manage を持つ。

    作成した直後、同じトークンのまま子の追加もポイントの記録もできる。
    """
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="こども")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, parent.headers, amount=5, reason="おてつだい", key="k1")


def test_child_cannot_create_a_family(client: TestClient, parent: Account) -> None:
    """子（guest ロール）は family:manage を持たないので、入口の scope で止まる。"""
    family_id = create_family(client, parent.headers)
    child_headers = _linked_child_headers(client, parent, family_id, username="taro")

    denied = client.post("/api/families", headers=child_headers, json={"name": "こどもの家"})
    assert denied.status_code == 403


def test_guest_cannot_accept_a_parent_invitation(
    client: TestClient, admin_headers: dict[str, str], parent: Account
) -> None:
    """親（parent）の招待を使えるのは保護者になれるアカウントだけ。

    未所属の guest は運用上は生まれない（ADR-0018）が、管理者が手動で作った
    場合でも「名ばかりの保護者」にはなれない。断られた招待コードは消費されず、
    正しい相手（member）が改めて使える。
    """
    family_id = create_family(client, parent.headers)
    outsider = create_account(client, admin_headers, username="visitor", role="guest")
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")

    denied = client.post(
        "/api/families/invitations/accept",
        headers=outsider.headers,
        json={"code": invitation["code"], "display_name": "なぞの人"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "guardian_account_required"

    aunt = create_account(client, admin_headers, username="aunt", role="member", display_name="おばさん")
    accepted = client.post(
        "/api/families/invitations/accept",
        headers=aunt.headers,
        json={"code": invitation["code"], "display_name": "おばさん"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "parent"


def test_removing_a_linked_child_deletes_the_account(client: TestClient, parent: Account) -> None:
    """除名は縁切り。子アカウントは家族の参加としてだけ存在するので、一緒に消す。"""
    family_id = create_family(client, parent.headers)
    child_headers = _linked_child_headers(client, parent, family_id, username="taro")
    detail = client.get(f"/api/families/{family_id}", headers=parent.headers).json()
    membership_id = next(m["id"] for m in detail["memberships"] if m["display_name"] == "taro")

    removed = client.delete(f"/api/families/{family_id}/memberships/{membership_id}", headers=parent.headers)
    assert removed.status_code == 204, removed.text

    # アカウントごと消えている: 古いトークンは無効、再ログインもできない
    assert client.get("/api/families", headers=child_headers).status_code == 401
    failed = client.post("/api/auth/login", json={"username": "taro", "password": "taro-pass-123"})
    assert failed.status_code == 401


def test_removing_an_unlinked_child_keeps_other_accounts(client: TestClient, parent: Account) -> None:
    """アカウントの無い子の除名は従来どおり参加と空の台帳だけを消す。"""
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    removed = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=parent.headers)
    assert removed.status_code == 204, removed.text

    # 親のアカウントは無事
    assert client.get("/api/families", headers=parent.headers).status_code == 200


def test_admin_has_no_family_access(client: TestClient, admin_headers: dict[str, str]) -> None:
    """システム管理者は家族・ポイントに関与しない（ADR-0018）。"""
    assert client.get("/api/families", headers=admin_headers).status_code == 403
    denied = client.post("/api/families", headers=admin_headers, json={"name": "かんりしゃの家"})
    assert denied.status_code == 403


def test_partial_guardian_scope_cannot_create_a_family(client: TestClient, admin_headers: dict[str, str]) -> None:
    """保護者の scope が一部欠けるカスタムロールでは家族を作れない。

    family:manage だけで通すと、閲覧も記録もできない owner が生まれてしまう。
    """
    created_role = client.post(
        "/api/admin/roles",
        headers=admin_headers,
        json={"name": "clerk", "permissions": ["gui:view", "family:view", "family:manage"]},
    )
    assert created_role.status_code == 201, created_role.text
    clerk = create_account(client, admin_headers, username="clerk1", role="clerk")

    denied = client.post("/api/families", headers=clerk.headers, json={"name": "しょきの家"})
    assert denied.status_code == 403


def test_existing_account_cannot_accept_a_child_invitation(
    client: TestClient, admin_headers: dict[str, str], parent: Account
) -> None:
    """子の招待コードは redeem（アカウント新規作成）専用。

    既存アカウントを子として結び付けられると、除名の後始末（アカウント削除）が
    独立に存在するアカウントを巻き込んでしまう。断られたコードは消費されず、
    本来の使い方（redeem）でそのまま使える。
    """
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    outsider = create_account(client, admin_headers, username="aunt", role="member")

    denied = client.post(
        "/api/families/invitations/accept",
        headers=outsider.headers,
        json={"code": invitation["code"], "display_name": "たろう？"},
    )
    assert denied.status_code == 400
    assert denied.json()["detail"]["error"] == "child_invitation_requires_signup"

    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text


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
