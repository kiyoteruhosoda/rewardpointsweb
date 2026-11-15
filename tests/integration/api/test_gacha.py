"""Gacha machines on a child's ledger (ADR-0060).

A parent sets up a machine (name, price, prizes with weights). One draw spends the price from
the ledger and wins one prize picked on the server. The parent marks real prizes as handed over.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bounded_contexts.reward_points.application.use_cases.draw_gacha import DrawGachaUseCase
from bounded_contexts.reward_points.presentation.dependencies import AccessDep, TransactionRepoDep
from bounded_contexts.reward_points.presentation.gacha_dependencies import (
    GachaDrawRepoDep,
    GachaRepoDep,
    get_draw_gacha_use_case,
)
from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)

_SNACKS: dict[str, object] = {
    "name": "おかしガチャ",
    "price": 30,
    "prizes": [
        {"name": "チョコ", "weight": 1},
        {"name": "グミ", "weight": 2},
        {"name": "はずれ", "weight": 1, "is_miss": True},
    ],
}


@dataclass(frozen=True, kw_only=True)
class Home:
    """A parent, their child's ledger, and a second child's ledger."""

    parent: Account
    ledger: Ledger
    child_membership_id: int
    sibling: Ledger

    @property
    def headers(self) -> dict[str, str]:
        return self.parent.headers


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    parent = create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="はなこ")
    sibling = add_child(client, parent.headers, family_id, display_name="じろう")
    return Home(
        parent=parent,
        ledger=Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))),
        child_membership_id=int(str(child["id"])),
        sibling=Ledger(family_id=family_id, ledger_id=int(str(sibling["ledger_id"]))),
    )


@pytest.fixture
def rolls(app: FastAPI) -> Iterator[list[int]]:
    """Fix the outcome of draws: each draw takes the next number (``0 .. total weight - 1``)."""
    queue: list[int] = []

    def build(
        *, access: AccessDep, gachas: GachaRepoDep, draws: GachaDrawRepoDep, transactions: TransactionRepoDep
    ) -> DrawGachaUseCase:
        return DrawGachaUseCase(
            access=access, gachas=gachas, draws=draws, transactions=transactions, roll=lambda _bound: queue.pop(0)
        )

    app.dependency_overrides[get_draw_gacha_use_case] = build
    yield queue
    app.dependency_overrides.pop(get_draw_gacha_use_case, None)


def _gachas_path(ledger: Ledger) -> str:
    return f"{ledger.path()}/gachas"


def _create(client: TestClient, home: Home, payload: dict[str, object] | None = None) -> dict[str, Any]:
    response = client.post(_gachas_path(home.ledger), headers=home.headers, json=payload or _SNACKS)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _draw_response(
    client: TestClient, ledger: Ledger, headers: dict[str, str], gacha: dict[str, Any], *, key: str
) -> Any:
    return client.post(f"{_gachas_path(ledger)}/{gacha['id']}/draws", headers=headers, json={"idempotency_key": key})


def _draw(client: TestClient, home: Home, gacha: dict[str, Any], *, key: str) -> dict[str, Any]:
    response = _draw_response(client, home.ledger, home.headers, gacha, key=key)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _board(client: TestClient, home: Home, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.get(_gachas_path(home.ledger), headers=headers or home.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _balance(client: TestClient, home: Home) -> int:
    response = client.get(home.ledger.path(), headers=home.headers)
    assert response.status_code == 200, response.text
    return int(response.json()["balance"])


def _error(response: Any) -> str:
    return str(response.json()["detail"]["error"])


def _child_headers(client: TestClient, home: Home) -> dict[str, str]:
    """Let the child sign in as themselves (invitation code, ADR-0011)."""
    invitation = issue_invitation(
        client, home.headers, home.ledger.family_id, role="child", target_membership_id=home.child_membership_id
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "hanako", "password": "hanako-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username="hanako", password="hanako-pass-123")


# --- Set up machines ----------------------------------------------------------------


def test_a_guardian_sets_up_a_machine_with_weighted_prizes(client: TestClient, home: Home) -> None:
    gacha = _create(client, home)

    assert gacha["name"] == "おかしガチャ"
    assert gacha["price"] == 30
    assert [(p["name"], p["weight"], p["is_miss"]) for p in gacha["prizes"]] == [
        ("チョコ", 1, False),
        ("グミ", 2, False),
        ("はずれ", 1, True),
    ]
    board = _board(client, home)
    assert board["display_name"] == "はなこ"
    assert board["can_modify"] is True
    assert board["can_draw"] is True
    assert [g["id"] for g in board["gachas"]] == [gacha["id"]]


def test_a_machine_of_only_misses_is_refused(client: TestClient, home: Home) -> None:
    response = client.post(
        _gachas_path(home.ledger),
        headers=home.headers,
        json={"name": "からっぽ", "price": 10, "prizes": [{"name": "はずれ", "weight": 1, "is_miss": True}]},
    )

    assert response.status_code == 400, response.text
    assert _error(response) == "gacha_needs_a_prize"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "ガチャ", "price": 10, "prizes": []},
        {"name": "ガチャ", "price": 0, "prizes": [{"name": "チョコ", "weight": 1}]},
        {"name": "ガチャ", "price": 10, "prizes": [{"name": "チョコ", "weight": 0}]},
        {"name": " ", "price": 10, "prizes": [{"name": "チョコ", "weight": 1}]},
        {"name": "ガチャ", "price": 10, "prizes": [{"name": "あ" * 51, "weight": 1}]},
    ],
)
def test_a_machine_that_cannot_work_is_refused(client: TestClient, home: Home, payload: dict[str, object]) -> None:
    response = client.post(_gachas_path(home.ledger), headers=home.headers, json=payload)

    assert response.status_code == 422, response.text


def test_editing_replaces_the_prizes_but_not_what_was_already_won(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(0)
    won = _draw(client, home, gacha, key="press-1")

    edited = client.put(
        f"{_gachas_path(home.ledger)}/{gacha['id']}",
        headers=home.headers,
        json={"name": "スペシャル", "price": 50, "prizes": [{"name": "えほん", "weight": 1}]},
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "スペシャル"
    assert [p["name"] for p in edited.json()["prizes"]] == ["えほん"]
    draw = _board(client, home)["draws"][0]
    assert draw["id"] == won["draw"]["id"]
    assert (draw["gacha_name"], draw["prize_name"], draw["price"]) == ("おかしガチャ", "チョコ", 30)


def test_deleting_a_machine_keeps_its_draws_and_the_points_spent(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(1)
    _draw(client, home, gacha, key="press-1")

    deleted = client.delete(f"{_gachas_path(home.ledger)}/{gacha['id']}", headers=home.headers)

    assert deleted.status_code == 204, deleted.text
    board = _board(client, home)
    assert board["gachas"] == []
    assert [(d["gacha_id"], d["prize_name"]) for d in board["draws"]] == [(None, "グミ")]
    assert _balance(client, home) == 70


# --- Draw -----------------------------------------------------------------------------


def test_a_draw_spends_the_price_in_the_ledger_and_wins_the_prize_the_roll_lands_on(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(2)  # Weights 1, 2, 1 -> rolls 1 and 2 land on the second prize

    result = _draw(client, home, gacha, key="press-1")

    assert result["draw"]["prize_name"] == "グミ"
    assert result["draw"]["is_miss"] is False
    assert result["draw"]["handed_over_at"] is None
    assert result["balance"] == 70
    ledger = client.get(home.ledger.path(), headers=home.headers).json()
    assert ledger["balance"] == 70
    newest = ledger["transactions"][0]
    assert (newest["amount"], newest["reason"]) == (-30, "おかしガチャ: グミ")


def test_resending_the_same_press_does_not_draw_twice(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.extend([0, 3])

    first = _draw(client, home, gacha, key="press-1")
    again = _draw(client, home, gacha, key="press-1")

    assert again["draw"] == first["draw"]
    assert _balance(client, home) == 70
    assert len(_board(client, home)["draws"]) == 1


def test_the_same_press_key_on_another_machine_is_refused(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    first = _create(client, home)
    second = _create(client, home, _SNACKS | {"name": "べつのガチャ"})
    rolls.append(0)
    _draw(client, home, first, key="press-1")

    response = _draw_response(client, home.ledger, home.headers, second, key="press-1")

    assert response.status_code == 409, response.text
    assert _error(response) == "idempotency_key_reused"


def test_a_draw_the_balance_cannot_cover_is_refused_and_writes_nothing(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.ledger.record(client, home.headers, amount=29, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(0)

    response = _draw_response(client, home.ledger, home.headers, gacha, key="press-1")

    assert response.status_code == 409, response.text
    assert _error(response) == "insufficient_balance"
    assert _balance(client, home) == 29
    assert _board(client, home)["draws"] == []


def test_a_draw_that_spends_the_last_point_is_allowed(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=30, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(3)

    result = _draw(client, home, gacha, key="press-1")

    assert result["draw"]["is_miss"] is True
    assert result["balance"] == 0


def test_a_machine_of_another_ledger_cannot_be_drawn_through_this_one(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.sibling.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(0)

    response = _draw_response(client, home.sibling, home.headers, gacha, key="press-1")

    assert response.status_code == 404, response.text
    assert _error(response) == "gacha_not_found"


# --- Who may draw (ADR-0060) ------------------------------------------------------------


def test_a_child_draws_on_their_own_ledger(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    child = _child_headers(client, home)
    board = _board(client, home, child)
    assert (board["can_modify"], board["can_draw"]) == (False, True)
    rolls.append(0)

    response = _draw_response(client, home.ledger, child, gacha, key="press-1")

    assert response.status_code == 201, response.text
    assert response.json()["draw"]["prize_name"] == "チョコ"
    assert _balance(client, home) == 70


def test_a_child_cannot_draw_on_a_siblings_ledger(client: TestClient, home: Home) -> None:
    home.sibling.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    sibling_gacha = client.post(_gachas_path(home.sibling), headers=home.headers, json=_SNACKS).json()
    child = _child_headers(client, home)

    response = _draw_response(client, home.sibling, child, sibling_gacha, key="press-1")

    assert response.status_code == 403, response.text
    assert _error(response) == "family_access_denied"


def test_a_child_cannot_set_up_or_edit_machines(client: TestClient, home: Home) -> None:
    gacha = _create(client, home)
    child = _child_headers(client, home)

    created = client.post(_gachas_path(home.ledger), headers=child, json=_SNACKS)
    edited = client.put(f"{_gachas_path(home.ledger)}/{gacha['id']}", headers=child, json=_SNACKS)
    deleted = client.delete(f"{_gachas_path(home.ledger)}/{gacha['id']}", headers=child)

    assert [created.status_code, edited.status_code, deleted.status_code] == [403, 403, 403]


def test_someone_outside_the_family_cannot_draw(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    stranger = create_account(client, admin_headers, username="stranger", role="member", display_name="よそのひと")

    response = _draw_response(client, home.ledger, stranger.headers, gacha, key="press-1")

    assert response.status_code == 403, response.text


# --- Hand over ---------------------------------------------------------------------------


def _handed_over_path(home: Home, draw: dict[str, Any]) -> str:
    return f"{home.ledger.path()}/gacha-draws/{draw['id']}/handed-over"


def test_a_guardian_marks_a_prize_handed_over_and_can_take_the_mark_back(
    client: TestClient, home: Home, rolls: list[int]
) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(0)
    draw = _draw(client, home, gacha, key="press-1")["draw"]

    marked = client.put(_handed_over_path(home, draw), headers=home.headers)
    again = client.put(_handed_over_path(home, draw), headers=home.headers)

    assert marked.status_code == 200, marked.text
    assert marked.json()["handed_over_at"] is not None
    # Marking twice keeps the first time
    assert again.json()["handed_over_at"] == marked.json()["handed_over_at"]
    assert _board(client, home)["draws"][0]["handed_over_at"] == marked.json()["handed_over_at"]

    taken_back = client.delete(_handed_over_path(home, draw), headers=home.headers)

    assert taken_back.status_code == 200, taken_back.text
    assert taken_back.json()["handed_over_at"] is None


def test_a_miss_cannot_be_handed_over(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(3)
    draw = _draw(client, home, gacha, key="press-1")["draw"]

    response = client.put(_handed_over_path(home, draw), headers=home.headers)

    assert response.status_code == 409, response.text
    assert _error(response) == "miss_cannot_be_handed_over"


def test_a_child_cannot_mark_their_own_prize_handed_over(client: TestClient, home: Home, rolls: list[int]) -> None:
    home.ledger.record(client, home.headers, amount=100, reason="おてつだい", key="k1")
    gacha = _create(client, home)
    rolls.append(0)
    draw = _draw(client, home, gacha, key="press-1")["draw"]
    child = _child_headers(client, home)

    response = client.put(_handed_over_path(home, draw), headers=child)

    assert response.status_code == 403, response.text
