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
)


@pytest.fixture
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


@pytest.fixture
def ledger(client: TestClient, parent: Account) -> Ledger:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    return Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))


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


def _correct(client: TestClient, headers: dict[str, str], ledger: Ledger, **body: object) -> Any:
    """訂正を送る。対象は ``transaction_id``、残りはそのまま本文になる。"""
    transaction_id = body.pop("transaction_id")
    return client.post(
        f"{ledger.path()}/transactions/{transaction_id}/corrections",
        headers=headers,
        json=body,
    )


def test_correction_undoes_the_original_and_writes_the_new_content(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    """訂正は書き換えではなく、打ち消しと書き直しの 2 行（ADR-0022）。"""
    original = ledger.record(client, parent.headers, amount=1000, reason="おてつだい", key="k1")

    response = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=100,
        reason="おてつだい",
        idempotency_key="k2",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reversal"]["amount"] == -1000
    assert body["reversal"]["reversal_of_id"] == original["id"]
    assert body["correction"]["amount"] == 100
    assert body["correction"]["corrects_id"] == original["id"]

    view = _view(client, parent.headers, ledger)
    assert view["balance"] == 100
    transactions = {t["id"]: t for t in view["transactions"]}
    # 元のレコードは消えず、取り消された印が付く
    assert len(transactions) == 3
    assert transactions[original["id"]]["is_reversed"] is True


def test_correction_keeps_the_original_moment(client: TestClient, parent: Account, ledger: Ledger) -> None:
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
    original = response.json()

    corrected = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=20,
        reason="せんしゅうのおてつだい",
        idempotency_key="k2",
    ).json()

    assert corrected["correction"]["occurred_at"] == original["occurred_at"]


def test_correction_may_move_the_moment(client: TestClient, parent: Account, ledger: Ledger) -> None:
    """日付の打ち間違いも直せる。"""
    original = ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")

    corrected = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=10,
        reason="おてつだい",
        idempotency_key="k2",
        occurred_at="2026-07-20T09:00:00+09:00",
    ).json()

    assert corrected["correction"]["occurred_at"].startswith("2026-07-20T00:00:00")


def test_correcting_an_already_reversed_record_is_rejected(client: TestClient, parent: Account, ledger: Ledger) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")
    client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k2"},
    )

    response = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=50,
        reason="まちがい",
        idempotency_key="k3",
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "transaction_already_reversed"


def test_correcting_a_reversal_is_rejected(client: TestClient, parent: Account, ledger: Ledger) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")
    reversal = client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k2"},
    ).json()

    response = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(reversal["id"])),
        amount=50,
        reason="まちがい",
        idempotency_key="k3",
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "correction_of_reversal_not_allowed"


def test_a_correction_can_be_corrected_again(client: TestClient, parent: Account, ledger: Ledger) -> None:
    original = ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="k1")
    first = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=50,
        reason="おてつだい",
        idempotency_key="k2",
    ).json()

    second = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(first["correction"]["id"])),
        amount=30,
        reason="おてつだい",
        idempotency_key="k3",
    )
    assert second.status_code == 201, second.text
    assert _view(client, parent.headers, ledger)["balance"] == 30


def test_resent_correction_is_refused_rather_than_applied_twice(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    """届き直しても二重に効かない（打ち消しの UNIQUE で先に止まる）。"""
    original = ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="k1")
    for _ in range(2):
        response = _correct(
            client,
            parent.headers,
            ledger,
            transaction_id=int(str(original["id"])),
            amount=50,
            reason="おてつだい",
            idempotency_key="same",
        )

    assert response.status_code == 409
    assert _view(client, parent.headers, ledger)["balance"] == 50


def test_correction_from_another_ledger_is_not_reachable(client: TestClient, parent: Account, ledger: Ledger) -> None:
    other = add_child(client, parent.headers, ledger.family_id, display_name="はなこ")
    other_ledger = Ledger(family_id=ledger.family_id, ledger_id=int(str(other["ledger_id"])))
    theirs = other_ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")

    response = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(theirs["id"])),
        amount=20,
        reason="おてつだい",
        idempotency_key="k2",
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "transaction_not_found"


def test_corrected_reason_replaces_the_mistaken_one_in_suggestions(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    """書き間違えた理由が候補に出続けると、同じ間違いを選び直してしまう。"""
    original = ledger.record(client, parent.headers, amount=100, reason="おてつだいい", key="k1")
    _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(original["id"])),
        amount=100,
        reason="おてつだい",
        idempotency_key="k2",
    )

    response = client.get(f"/api/families/{ledger.family_id}/reason-suggestions", headers=parent.headers)
    assert response.json() == ["おてつだい"]


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
