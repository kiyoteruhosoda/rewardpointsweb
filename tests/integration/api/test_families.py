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


# --- 家族の作成と保護者への昇格（ADR-0017） ----------------------------------


@pytest.fixture
def newcomer(client: TestClient, admin_headers: dict[str, str]) -> Account:
    """どの家族にも所属していない、閲覧専用ロール（member）のアカウント。"""
    return create_account(client, admin_headers, username="newcomer", role="member", display_name="しんじん")


def test_member_can_create_a_family_and_becomes_a_guardian(client: TestClient, newcomer: Account) -> None:
    created = client.post("/api/families", headers=newcomer.headers, json={"name": "しんじんの家"})
    assert created.status_code == 201, created.text
    assert created.json()["my_role"] == "owner"

    # scope はトークンに焼き込まれているため、昇格した権限は再ログインで有効になる
    family_id = int(str(created.json()["id"]))
    fresh_headers = login(client, username=newcomer.username, password=newcomer.password)
    child = add_child(client, fresh_headers, family_id, display_name="こども")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, fresh_headers, amount=5, reason="おてつだい", key="k1")


def test_guest_cannot_create_a_family(client: TestClient, admin_headers: dict[str, str]) -> None:
    """guest ロールは family:view を持たないので、入口の scope で止まる。"""
    guest = create_account(client, admin_headers, username="visitor", role="guest")

    denied = client.post("/api/families", headers=guest.headers, json={"name": "つくれない"})
    assert denied.status_code == 403


def test_child_in_a_family_cannot_create_another(client: TestClient, parent: Account) -> None:
    """子も member ロール（family:view）を持つが、所属がある限り作れない（ADR-0013）。"""
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    child_headers = login(client, username="taro", password="taro-pass-123")

    denied = client.post("/api/families", headers=child_headers, json={"name": "こどもの家"})
    assert denied.status_code == 409
    assert denied.json()["detail"]["error"] == "already_belongs_to_family"


def test_member_who_accepts_a_parent_invitation_becomes_a_guardian(
    client: TestClient, admin_headers: dict[str, str], parent: Account
) -> None:
    family_id = create_family(client, parent.headers)
    aunt = create_account(client, admin_headers, username="aunt", role="member", display_name="おばさん")
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")

    accepted = client.post(
        "/api/families/invitations/accept",
        headers=aunt.headers,
        json={"code": invitation["code"], "display_name": "おばさん"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "parent"

    # 再ログイン後は保護者としてポイントを記録できる
    fresh_headers = login(client, username=aunt.username, password=aunt.password)
    child = add_child(client, fresh_headers, family_id, display_name="めい")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, fresh_headers, amount=3, reason="おてつだい", key="k1")


def test_admin_who_creates_a_family_keeps_a_single_role(client: TestClient, admin_headers: dict[str, str]) -> None:
    """保護者相当の scope を既に持つアカウントには、manager ロールを重ねて付与しない。"""
    created = client.post("/api/families", headers=admin_headers, json={"name": "かんりしゃの家"})
    assert created.status_code == 201, created.text

    users = client.get("/api/admin/users", headers=admin_headers).json()
    admin = next(user for user in users if user["username"] == "admin@example.com")
    assert admin["roles"] == ["admin"]


def _create_custom_role(client: TestClient, admin_headers: dict[str, str], *, name: str, scopes: list[str]) -> None:
    response = client.post(
        "/api/admin/roles",
        headers=admin_headers,
        json={"name": name, "permissions": scopes},
    )
    assert response.status_code == 201, response.text


def _roles_of(client: TestClient, admin_headers: dict[str, str], username: str) -> list[str]:
    users = client.get("/api/admin/users", headers=admin_headers).json()
    roles: list[str] = next(user for user in users if user["username"] == username)["roles"]
    return roles


def test_partial_guardian_scopes_still_get_promoted(client: TestClient, admin_headers: dict[str, str]) -> None:
    """保護者の scope が一部欠けるカスタムロールでも、作成時に manager が付く。

    family:manage だけで判定すると、point:manage の無い owner が生まれてしまう。
    """
    _create_custom_role(client, admin_headers, name="clerk", scopes=["gui:view", "family:view", "family:manage"])
    creator = create_account(client, admin_headers, username="clerk1", role="clerk")

    created = client.post("/api/families", headers=creator.headers, json={"name": "しょきの家"})
    assert created.status_code == 201, created.text
    assert sorted(_roles_of(client, admin_headers, creator.username)) == ["clerk", "manager"]

    # 再ログイン後はポイントも記録できる
    family_id = int(str(created.json()["id"]))
    fresh_headers = login(client, username=creator.username, password=creator.password)
    child = add_child(client, fresh_headers, family_id, display_name="こども")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, fresh_headers, amount=1, reason="おてつだい", key="k1")


def test_full_guardian_scopes_keep_roles_untouched(client: TestClient, admin_headers: dict[str, str]) -> None:
    """保護者の scope が全て揃っているなら、member を含めロール構成へ触れない。

    判定より先に member を外すと、保護者側のロールが持たない scope（閲覧等）を
    黙って失い得る。
    """
    _create_custom_role(
        client,
        admin_headers,
        name="head",
        scopes=["family:view", "family:manage", "point:view", "point:manage"],
    )
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "head1",
            "display_name": "head1",
            "password": "head1-pass-123",
            "roles": ["head", "member"],
        },
    )
    assert response.status_code == 201, response.text
    headers = login(client, username="head1", password="head1-pass-123")

    created = client.post("/api/families", headers=headers, json={"name": "とうしゅの家"})
    assert created.status_code == 201, created.text
    assert sorted(_roles_of(client, admin_headers, "head1")) == ["head", "member"]


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
