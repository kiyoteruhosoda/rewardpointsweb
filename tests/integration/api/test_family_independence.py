"""ゲスト（子）の独立 — 親メンバーが指示し、子本人が承認して成立する（ADR-0014）。

成立すると参加・台帳・記録は家族から消え、アカウントは所属なしのメンバーとなる
（自分の家族を作ることも、招待をメンバーとして受け直すこともできる）。
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
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="manager", display_name="おとうさん")


def _linked_child(
    client: TestClient, parent: Account, family_id: int, *, username: str = "taro"
) -> tuple[int, dict[str, str]]:
    """アカウントの結び付いた子を用意し、(membership_id, 子のヘッダ) を返す。"""
    child = add_child(client, parent.headers, family_id, display_name=username)
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": f"{username}-pass-123"},
    )
    assert response.status_code == 201, response.text
    return int(str(child["id"])), login(client, username=username, password=f"{username}-pass-123")


def _propose(client: TestClient, headers: dict[str, str], family_id: int, membership_id: int) -> None:
    response = client.post(
        f"/api/families/{family_id}/memberships/{membership_id}/independence-proposal",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["independence_proposed"] is True


# --- 指示 --------------------------------------------------------------------


def test_parent_proposes_and_the_family_sees_it(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    membership_id, child_headers = _linked_child(client, parent, family_id)

    _propose(client, parent.headers, family_id, membership_id)

    # 子本人にも承認待ちであることが見える
    detail = client.get(f"/api/families/{family_id}", headers=child_headers).json()
    me = next(m for m in detail["memberships"] if m["is_me"])
    assert me["independence_proposed"] is True


def test_unlinked_child_cannot_be_proposed(client: TestClient, parent: Account) -> None:
    """アカウントの無い子は承認のしようがない（除名を使う）。"""
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    response = client.post(
        f"/api/families/{family_id}/memberships/{child['id']}/independence-proposal",
        headers=parent.headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "membership_not_linked"


def test_independence_cannot_be_proposed_for_a_parent(
    client: TestClient, admin_headers: dict[str, str], parent: Account
) -> None:
    family_id = create_family(client, parent.headers)
    other = create_account(client, admin_headers, username="mom", role="manager")
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")
    accepted = client.post(
        "/api/families/invitations/accept",
        headers=other.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )

    response = client.post(
        f"/api/families/{family_id}/memberships/{accepted.json()['membership_id']}/independence-proposal",
        headers=parent.headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "child_account_required"


def test_child_cannot_propose_independence(client: TestClient, parent: Account) -> None:
    """指示できるのは親メンバーだけ。子は scope（family:manage 無し）で止まる。"""
    family_id = create_family(client, parent.headers)
    membership_id, child_headers = _linked_child(client, parent, family_id)

    response = client.post(
        f"/api/families/{family_id}/memberships/{membership_id}/independence-proposal",
        headers=child_headers,
    )
    assert response.status_code == 403


# --- 承認と成立 --------------------------------------------------------------


def test_approval_without_a_proposal_is_refused(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    _, child_headers = _linked_child(client, parent, family_id)

    response = client.post(f"/api/families/{family_id}/independence", headers=child_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "independence_not_proposed"


def test_revoked_proposal_cannot_be_approved(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    membership_id, child_headers = _linked_child(client, parent, family_id)
    _propose(client, parent.headers, family_id, membership_id)

    revoked = client.delete(
        f"/api/families/{family_id}/memberships/{membership_id}/independence-proposal",
        headers=parent.headers,
    )
    assert revoked.status_code == 204

    response = client.post(f"/api/families/{family_id}/independence", headers=child_headers)
    assert response.status_code == 409


def test_approved_independence_removes_the_guest_and_frees_the_account(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    membership_id, child_headers = _linked_child(client, parent, family_id)
    detail = client.get(f"/api/families/{family_id}", headers=parent.headers).json()
    ledger_id = next(m for m in detail["memberships"] if m["id"] == membership_id)["ledger_id"]
    ledger = Ledger(family_id=family_id, ledger_id=int(str(ledger_id)))
    ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")
    _propose(client, parent.headers, family_id, membership_id)

    approved = client.post(f"/api/families/{family_id}/independence", headers=child_headers)
    assert approved.status_code == 204

    # 家族から消える: 名簿に居ない・台帳も記録ごと無い
    names = [
        m["display_name"]
        for m in client.get(f"/api/families/{family_id}", headers=parent.headers).json()["memberships"]
    ]
    assert names == ["おとうさん"]
    assert client.get(ledger.path(), headers=parent.headers).status_code == 404

    # 所属なしのメンバーとなる: 一覧は空になる
    assert client.get("/api/families", headers=child_headers).json() == []

    # scope はトークンに焼き込まれているため、昇格した権限は再ログインで有効になる
    fresh_headers = login(client, username="taro", password="taro-pass-123")
    created = client.post("/api/families", headers=fresh_headers, json={"name": "たろうの家"})
    assert created.status_code == 201, created.text
    assert created.json()["my_role"] == "owner"


def test_independent_account_can_rejoin_as_a_member(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    membership_id, child_headers = _linked_child(client, parent, family_id)
    _propose(client, parent.headers, family_id, membership_id)
    assert client.post(f"/api/families/{family_id}/independence", headers=child_headers).status_code == 204

    # 元の家族から、今度はメンバー（parent）として招待を受け直せる
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")
    rejoined = client.post(
        "/api/families/invitations/accept",
        headers=child_headers,
        json={"code": invitation["code"], "display_name": "たろう（おとな）"},
    )
    assert rejoined.status_code == 200, rejoined.text
    assert rejoined.json()["role"] == "parent"


def test_parent_cannot_approve_independence(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)

    response = client.post(f"/api/families/{family_id}/independence", headers=parent.headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"
