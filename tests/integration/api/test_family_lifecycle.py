"""家族の一生 — 改名・脱退・解散（ADR-0013）。

- 家族名は owner だけが変えられる。
- 親は他に親が残るなら抜けられ、抜けた後は初期状態（作り直しも招待の受け直しもできる）。
- owner が抜けると最も古い parent が owner を引き継ぐ。
- 子（ゲスト）は自分では抜けられない。
- 解散は owner のみ、自分以外の参加者がいない場合だけ。
"""

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
def owner(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="manager", display_name="おとうさん")


@pytest.fixture
def second_parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="mom", role="manager", display_name="おかあさん")


def _join_as_parent(client: TestClient, owner: Account, family_id: int, *, joiner: Account, name: str) -> int:
    invitation = issue_invitation(client, owner.headers, family_id, role="parent")
    response = client.post(
        "/api/families/invitations/accept",
        headers=joiner.headers,
        json={"code": invitation["code"], "display_name": name},
    )
    assert response.status_code == 200, response.text
    membership_id: int = response.json()["membership_id"]
    return membership_id


def _child_login(client: TestClient, owner: Account, family_id: int, *, username: str) -> dict[str, str]:
    child = add_child(client, owner.headers, family_id, display_name=username)
    invitation = issue_invitation(
        client, owner.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": f"{username}-pass-123"},
    )
    assert response.status_code == 201, response.text
    return login(client, username=username, password=f"{username}-pass-123")


# --- 改名 --------------------------------------------------------------------


def test_owner_renames_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers, name="ほその家")

    response = client.patch(f"/api/families/{family_id}", headers=owner.headers, json={"name": "あたらしい家"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "あたらしい家"

    listed = client.get("/api/families", headers=owner.headers).json()
    assert [family["name"] for family in listed] == ["あたらしい家"]


def test_parent_cannot_rename_the_family(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.patch(f"/api/families/{family_id}", headers=second_parent.headers, json={"name": "のっとり"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"


def test_blank_family_name_is_rejected(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)

    assert client.patch(f"/api/families/{family_id}", headers=owner.headers, json={"name": "  "}).status_code == 422


# --- 脱退 --------------------------------------------------------------------


def test_parent_leaves_and_returns_to_the_initial_state(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    left = client.post(f"/api/families/{family_id}/leave", headers=second_parent.headers)
    assert left.status_code == 204

    # 初期状態と同じ: 所属は無く、元の家族には届かない（縁が切れる）
    assert client.get("/api/families", headers=second_parent.headers).json() == []
    assert client.get(f"/api/families/{family_id}", headers=second_parent.headers).status_code == 403
    # 作り直すことも、招待を受け直すこともできる
    assert client.post("/api/families", headers=second_parent.headers, json={"name": "じぶんの家"}).status_code == 201


def test_leaving_parent_disappears_from_history_but_records_remain(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    child = add_child(client, owner.headers, family_id, display_name="たろう")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, second_parent.headers, amount=10, reason="おてつだい", key="k1")

    assert client.post(f"/api/families/{family_id}/leave", headers=second_parent.headers).status_code == 204

    view = client.get(ledger.path(), headers=owner.headers).json()
    # 記録は台帳のものとして残り、操作者への参照だけが外れる
    assert view["balance"] == 10
    assert [t["granted_by"] for t in view["transactions"]] == [None]


def test_leaving_owner_hands_the_family_to_the_oldest_parent(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    assert client.post(f"/api/families/{family_id}/leave", headers=owner.headers).status_code == 204

    detail = client.get(f"/api/families/{family_id}", headers=second_parent.headers).json()
    assert detail["my_role"] == "owner"
    assert [m["display_name"] for m in detail["memberships"]] == ["おかあさん"]


def test_owner_cannot_leave_when_the_other_parent_lost_their_account(
    *, client: TestClient, admin_headers: dict[str, str], owner: Account, second_parent: Account
) -> None:
    """アカウントの消えた親（未紐付けの参加）は「残る親」に数えない。

    数えてしまうと、owner の脱退が誰もログインできない owner を生み、家族を
    管理も解散もできなくしてしまう。
    """
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    assert client.delete(f"/api/admin/users/{second_parent.user_id}", headers=admin_headers).status_code == 204

    response = client.post(f"/api/families/{family_id}/leave", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "last_guardian_cannot_leave"


def test_leaving_owner_skips_parents_without_an_account(
    *, client: TestClient, admin_headers: dict[str, str], owner: Account, second_parent: Account
) -> None:
    """引き継ぎ先は、古さより先にアカウントの結び付きで絞る。"""
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    grandma = create_account(client, admin_headers, username="grandma", role="manager")
    _join_as_parent(client, owner, family_id, joiner=grandma, name="おばあちゃん")
    assert client.delete(f"/api/admin/users/{second_parent.user_id}", headers=admin_headers).status_code == 204

    assert client.post(f"/api/families/{family_id}/leave", headers=owner.headers).status_code == 204

    # より古い「おかあさん」はアカウントが無いので飛ばし、おばあちゃんが owner になる
    detail = client.get(f"/api/families/{family_id}", headers=grandma.headers).json()
    assert detail["my_role"] == "owner"


def test_the_last_parent_cannot_leave(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)
    add_child(client, owner.headers, family_id, display_name="たろう")

    response = client.post(f"/api/families/{family_id}/leave", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "last_guardian_cannot_leave"


def test_child_cannot_leave_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)
    child_headers = _child_login(client, owner, family_id, username="taro")

    response = client.post(f"/api/families/{family_id}/leave", headers=child_headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "child_cannot_leave_family"


# --- 解散 --------------------------------------------------------------------


def test_owner_alone_dissolves_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 204

    # 初期状態と同じ: 一覧は空になり、作り直せる
    assert client.get("/api/families", headers=owner.headers).json() == []
    assert client.post("/api/families", headers=owner.headers, json={"name": "つぎの家"}).status_code == 201


def test_family_with_a_member_cannot_be_dissolved(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "family_not_empty"


def test_family_with_a_guest_cannot_be_dissolved(client: TestClient, owner: Account) -> None:
    """子（ゲスト）が残っていても解散できない。台帳ごと消える経路を作らない。"""
    family_id = create_family(client, owner.headers)
    add_child(client, owner.headers, family_id, display_name="たろう")

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "family_not_empty"


def test_parent_cannot_dissolve_the_family(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.delete(f"/api/families/{family_id}", headers=second_parent.headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"
