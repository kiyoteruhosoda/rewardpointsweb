"""追記型のポイント台帳（ADR-0010）。"""

from __future__ import annotations

from typing import Any

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
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


@pytest.fixture
def ledger(client: TestClient, parent: Account) -> Ledger:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    return Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))


@pytest.fixture
def co_parent(*, client: TestClient, admin_headers: dict[str, str], parent: Account, ledger: Ledger) -> Account:
    """招待で加わった、owner ではない親（`role = parent`）。"""
    joined = create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")
    invitation = issue_invitation(client, parent.headers, ledger.family_id, role="parent")
    response = client.post(
        "/api/families/invitations/accept",
        headers=joined.headers,
        json={"code": invitation["code"]},
    )
    assert response.status_code == 200, response.text
    return joined


def _view(client: TestClient, headers: dict[str, str], ledger: Ledger) -> dict[str, Any]:
    response = client.get(ledger.path(), headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_balance_is_the_sum_of_the_ledger(client: TestClient, parent: Account, ledger: Ledger) -> None:
    ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="k1")
    ledger.record(client, parent.headers, amount=-30, reason="おかし", key="k2")

    assert _view(client, parent.headers, ledger)["balance"] == 70


def test_balance_may_go_negative(client: TestClient, parent: Account, ledger: Ledger) -> None:
    """前借りの運用を認める（消費時の残高検証は行わない）。"""
    ledger.record(client, parent.headers, amount=-50, reason="まえがり", key="k1")

    assert _view(client, parent.headers, ledger)["balance"] == -50


def test_zero_amount_is_rejected(client: TestClient, parent: Account, ledger: Ledger) -> None:
    response = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={"amount": 0, "reason": "なにもしない", "idempotency_key": "k1"},
    )
    assert response.status_code == 422


def test_same_idempotency_key_returns_the_first_record(client: TestClient, parent: Account, ledger: Ledger) -> None:
    """送信ボタンの二重タップで二重登録しない。"""
    first = ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="same")
    second = ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="same")

    assert first["id"] == second["id"]
    view = _view(client, parent.headers, ledger)
    assert view["balance"] == 100
    assert len(list(view["transactions"])) == 1


def test_reversal_adds_an_opposite_row_and_keeps_the_original(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")

    response = client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k2"},
    )
    assert response.status_code == 201, response.text
    reversal = response.json()
    assert reversal["amount"] == -100
    # 理由は元のレコードから引き継ぐ
    assert reversal["reason"] == "まちがい"
    assert reversal["reversal_of_id"] == original["id"]

    view = _view(client, parent.headers, ledger)
    assert view["balance"] == 0
    transactions = {t["id"]: t for t in view["transactions"]}
    # 元のレコードは消えず、「取り消された」印が付く
    assert len(transactions) == 2
    assert transactions[original["id"]]["is_reversed"] is True


def test_a_parent_who_joined_by_invitation_reverses_the_owners_record(
    *, client: TestClient, parent: Account, co_parent: Account, ledger: Ledger
) -> None:
    """取り消しは owner の特権ではない（ADR-0009 の認可表）。

    記録を付けた本人でなくても、同じ家族の親なら取り消せる。日々の記録は
    どちらの親も付けるので、間違いを直すのに付けた本人の帰りを待たせない。
    """
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")

    # 画面の出し分けもこの値だけで決まるので、取り消しボタンが出ることまで含めて確かめる
    assert _view(client, co_parent.headers, ledger)["can_modify"] is True

    response = client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=co_parent.headers,
        json={"idempotency_key": "k2"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == -100
    # 打ち消しの行に残るのは取り消した側の親（記録を付けた親ではない）
    assert response.json()["granted_by"] == "おかあさん"
    assert _view(client, co_parent.headers, ledger)["balance"] == 0


def test_double_reversal_is_rejected(client: TestClient, parent: Account, ledger: Ledger) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")
    path = f"{ledger.path()}/transactions/{original['id']}/reversals"
    client.post(path, headers=parent.headers, json={"idempotency_key": "k2"})

    again = client.post(path, headers=parent.headers, json={"idempotency_key": "k3"})
    assert again.status_code == 409
    assert again.json()["detail"]["error"] == "transaction_already_reversed"


def test_reversal_of_a_reversal_is_rejected(client: TestClient, parent: Account, ledger: Ledger) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")
    reversal = client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k2"},
    ).json()

    response = client.post(
        f"{ledger.path()}/transactions/{reversal['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k3"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "reversal_of_reversal_not_allowed"


def test_transactions_from_another_ledger_are_not_reachable(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    other = add_child(client, parent.headers, ledger.family_id, display_name="はなこ")
    other_ledger = Ledger(family_id=ledger.family_id, ledger_id=int(str(other["ledger_id"])))
    theirs = other_ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")

    response = client.post(
        f"{ledger.path()}/transactions/{theirs['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k2"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "transaction_not_found"


def test_backdated_occurred_at_is_accepted(client: TestClient, parent: Account, ledger: Ledger) -> None:
    response = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={
            "amount": 10,
            "reason": "せんしゅうのおてつだい",
            "idempotency_key": "k1",
            "occurred_at": "2026-07-20T09:00:00+09:00",
        },
    )
    assert response.status_code == 201, response.text
    # tz 付きで届いても UTC の naive datetime へ揃える
    assert response.json()["occurred_at"].startswith("2026-07-20T00:00:00")
