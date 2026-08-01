"""家族が出来上がるまでの一続きの流れ（E2E）。

個々の入口は他のテストが細かく見ている。ここで見るのは **繋がり** —
管理者がメンバーを作るところから、子ども本人が自分のポイントを見るまでを、
実際に利用者が辿る順で 1 度だけ通す。

    システム管理者がメンバーを作る
      → メンバーがログインして家族を作り、子ども 1 人目を追加する
      → メンバーがもう 1 人の親を招待する
      → 招待された親がコードでアカウントを作り、家族へ加わる
      → 招待された親が子ども 2 人目を追加し、子ども 1 人目にポイントを足す
      → 招待された親が子ども 1 人目へ招待リンクを渡す
      → 子ども 1 人目がコードでアカウントを作り、ログインして自分の残高を見る

途中の状態を DB から覗かず、API だけで組み立てる。実際の利用者が通れない順路が
あれば、ここで落ちる。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.family_support import Account, create_account, login

_FIRST_CHILD = "はなこ"
_SECOND_CHILD = "たろう"
_POINTS = 30


@pytest.fixture
def member(client: TestClient, admin_headers: dict[str, str]) -> Account:
    """システム管理者がメンバー（親）のアカウントを作る。"""
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


def _start_a_family(client: TestClient, member: Account) -> tuple[int, dict[str, object]]:
    """メンバーが家族を作り、子ども 1 人目を追加する。"""
    created = client.post("/api/families", headers=member.headers, json={"name": "ほその家"})
    assert created.status_code == 201, created.text
    family_id = int(str(created.json()["id"]))
    assert created.json()["my_role"] == "owner"

    child = client.post(
        f"/api/families/{family_id}/memberships",
        headers=member.headers,
        json={"display_name": _FIRST_CHILD},
    )
    assert child.status_code == 201, child.text
    # 追加と同時に台帳ができる。本人はまだログインできない
    assert child.json()["ledger_id"] is not None
    assert child.json()["is_linked"] is False
    return family_id, child.json()


def _invite(
    client: TestClient,
    inviter: Account,
    family_id: int,
    *,
    role: str,
    target_membership_id: int | None = None,
) -> str:
    """招待コードを発行する。平文のコードが返るのはこの応答だけ。"""
    issued = client.post(
        f"/api/families/{family_id}/invitations",
        headers=inviter.headers,
        json={"role": role, "target_membership_id": target_membership_id},
    )
    assert issued.status_code == 201, issued.text
    code: str = str(issued.json()["code"])
    return code


def _sign_up_with(client: TestClient, code: str, *, username: str, display_name: str) -> Account:
    """招待コードでアカウントを作り、そのまま家族へ加わってログインする。"""
    password = f"{username}-pass-123"
    signed_up = client.post(
        "/api/families/invitations/redeem",
        json={
            "code": code,
            "username": username,
            "password": password,
            "display_name": display_name,
        },
    )
    assert signed_up.status_code == 201, signed_up.text
    return Account(
        user_id=0,
        username=username,
        password=password,
        headers=login(client, username=username, password=password),
    )


def _member_of(client: TestClient, viewer: Account, family_id: int, *, name: str) -> dict[str, object]:
    detail = client.get(f"/api/families/{family_id}", headers=viewer.headers)
    assert detail.status_code == 200, detail.text
    found: dict[str, object] = next(m for m in detail.json()["memberships"] if m["display_name"] == name)
    return found


def test_a_family_comes_together_from_scratch(client: TestClient, member: Account) -> None:
    family_id, first_child = _start_a_family(client, member)

    # --- もう 1 人の親を招く -------------------------------------------------
    parent_code = _invite(client, member, family_id, role="parent")
    invited = _sign_up_with(client, parent_code, username="mom", display_name="おかあさん")

    joined = client.get(f"/api/families/{family_id}", headers=invited.headers)
    assert joined.status_code == 200, joined.text
    assert joined.json()["my_role"] == "parent"

    # --- 招待された親が家族を育てる -----------------------------------------
    second = client.post(
        f"/api/families/{family_id}/memberships",
        headers=invited.headers,
        json={"display_name": _SECOND_CHILD},
    )
    assert second.status_code == 201, second.text

    ledger_id = int(str(first_child["ledger_id"]))
    recorded = client.post(
        f"/api/families/{family_id}/ledgers/{ledger_id}/transactions",
        headers=invited.headers,
        json={"amount": _POINTS, "reason": "おてつだい", "idempotency_key": "e2e-1"},
    )
    assert recorded.status_code == 201, recorded.text

    # --- 子ども本人がログインできるようにする --------------------------------
    child_code = _invite(
        client,
        invited,
        family_id,
        role="child",
        target_membership_id=int(str(first_child["id"])),
    )
    child = _sign_up_with(client, child_code, username="hanako", display_name=_FIRST_CHILD)

    # --- 子ども本人が自分のポイントを見る ------------------------------------
    ledger = client.get(f"/api/families/{family_id}/ledgers/{ledger_id}", headers=child.headers)
    assert ledger.status_code == 200, ledger.text
    assert ledger.json()["balance"] == _POINTS
    assert [row["reason"] for row in ledger.json()["transactions"]] == ["おてつだい"]
    # 見えるだけで、自分では書き換えられない（ADR-0007）
    assert ledger.json()["can_modify"] is False

    # 兄弟の残高は見えない。名簿には並ぶが台帳への入り口は無い（ADR-0009）
    sibling = _member_of(client, child, family_id, name=_SECOND_CHILD)
    assert sibling["ledger_id"] is None
    assert sibling["balance"] is None
