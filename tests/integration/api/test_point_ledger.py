"""Append-only point ledger (ADR-0010)."""

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
    """A non-owner parent who joined by invitation (`role = parent`)."""
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
    """Borrowing ahead is allowed (no balance check on spending)."""
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
    """A double tap on the submit button does not register twice."""
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
    # The reason is carried over from the original record
    assert reversal["reason"] == "まちがい"
    assert reversal["reversal_of_id"] == original["id"]

    view = _view(client, parent.headers, ledger)
    assert view["balance"] == 0
    transactions = {t["id"]: t for t in view["transactions"]}
    # The original record is not deleted; it gets a "reversed" mark
    assert len(transactions) == 2
    assert transactions[original["id"]]["is_reversed"] is True


def test_a_parent_who_joined_by_invitation_reverses_the_owners_record(
    *, client: TestClient, parent: Account, co_parent: Account, ledger: Ledger
) -> None:
    """Reversing is not an owner privilege (ADR-0009 authorization table).

    Any parent of the same family can reverse, not just the one who recorded it. Both
    parents record day to day, so fixing a mistake should not wait for the recorder.
    """
    original = ledger.record(client, parent.headers, amount=100, reason="まちがい", key="k1")

    # The UI decides what to show from this value alone, so also check that the undo button appears
    assert _view(client, co_parent.headers, ledger)["can_modify"] is True

    response = client.post(
        f"{ledger.path()}/transactions/{original['id']}/reversals",
        headers=co_parent.headers,
        json={"idempotency_key": "k2"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == -100
    # The reversal row records the parent who reversed it (not the one who recorded it)
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


def _correct(client: TestClient, headers: dict[str, str], ledger: Ledger, **body: object) -> Any:
    """Send a correction. The target is ``transaction_id``; the rest becomes the body as is."""
    transaction_id = body.pop("transaction_id")
    return client.post(
        f"{ledger.path()}/transactions/{transaction_id}/corrections",
        headers=headers,
        json=body,
    )


def test_correction_undoes_the_original_and_writes_the_new_content(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    """A correction is not an overwrite but 2 rows: a reversal and a rewrite (ADR-0022)."""
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
    # The original record is not deleted; it gets a reversed mark
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
    """A mistyped date can be fixed too."""
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
    """A redelivery does not apply twice (the reversal's UNIQUE stops it first)."""
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


def test_step_shaped_keys_are_refused_by_the_ordinary_endpoints(
    client: TestClient, parent: Account, ledger: Ledger
) -> None:
    """The key shape a correction builds internally cannot be written from outside.

    If it could, that row would share its key with the correction's reversal row and
    ``append`` would return an unrelated existing row, leaving the reversal unwritten
    while appearing to be written.
    """
    response = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={"amount": 100, "reason": "おてつだい", "idempotency_key": "k1#reversal"},
    )
    assert response.status_code == 422


def test_the_same_key_cannot_correct_two_different_records(client: TestClient, parent: Account, ledger: Ledger) -> None:
    """Even if a key is reused for correcting another record, no correction is left without its reversal."""
    first = ledger.record(client, parent.headers, amount=100, reason="おてつだい", key="k1")
    second = ledger.record(client, parent.headers, amount=200, reason="そうじ", key="k2")
    _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(first["id"])),
        amount=50,
        reason="おてつだい",
        idempotency_key="same",
    )

    response = _correct(
        client,
        parent.headers,
        ledger,
        transaction_id=int(str(second["id"])),
        amount=20,
        reason="そうじ",
        idempotency_key="same",
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "idempotency_key_reused"
    # The 2nd one leaves neither a reversal nor a corrected row (50 + 200)
    assert _view(client, parent.headers, ledger)["balance"] == 250


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
    """If a misspelled reason keeps showing up as a suggestion, people pick the same mistake again."""
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
    # Even when it arrives tz-aware, it is normalized to a naive UTC datetime
    assert response.json()["occurred_at"].startswith("2026-07-20T00:00:00")
