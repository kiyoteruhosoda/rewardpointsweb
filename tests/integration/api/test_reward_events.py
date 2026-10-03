"""イベント（がんばりカード。ADR-0042）。

目標・達成でもらえるポイント・達成回数を決めて作り、1 回達成するたびにシールを
1 枚貼る。マスが全部埋まったら、台帳へ達成のポイントが 1 行入る。
"""

from __future__ import annotations

from dataclasses import dataclass
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
    login,
)


@dataclass(frozen=True, kw_only=True)
class Home:
    """親と、その子の台帳。"""

    parent: Account
    ledger: Ledger
    child_membership_id: int

    @property
    def headers(self) -> dict[str, str]:
        return self.parent.headers


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    parent = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    return Home(
        parent=parent,
        ledger=Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))),
        child_membership_id=int(str(child["id"])),
    )


def _events_path(ledger: Ledger) -> str:
    return f"{ledger.path()}/events"


def _create(
    client: TestClient,
    home: Home,
    *,
    title: str = "はみがき",
    reward_points: int = 50,
    goal_count: int = 3,
) -> dict[str, Any]:
    response = client.post(
        _events_path(home.ledger),
        headers=home.headers,
        json={"title": title, "reward_points": reward_points, "goal_count": goal_count},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _sticker_path(home: Home, event: dict[str, Any], number: int) -> str:
    return f"{_events_path(home.ledger)}/{event['id']}/stickers/{number}"


def _stick(client: TestClient, home: Home, event: dict[str, Any], *, number: int) -> dict[str, Any]:
    response = client.put(_sticker_path(home, event, number), headers=home.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _ledger(client: TestClient, home: Home) -> dict[str, Any]:
    response = client.get(home.ledger.path(), headers=home.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _child_headers(client: TestClient, home: Home) -> dict[str, str]:
    """その子として本人ログインできるようにする（招待コード。ADR-0011）。"""
    invitation = issue_invitation(
        client, home.headers, home.ledger.family_id, role="child", target_membership_id=home.child_membership_id
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username="taro", password="taro-pass-123")


# --- 作る・見る ----------------------------------------------------------------


def test_a_guardian_makes_a_card_with_empty_squares(client: TestClient, home: Home) -> None:
    event = _create(client, home, title="はみがき", reward_points=50, goal_count=10)

    assert event["title"] == "はみがき"
    assert event["reward_points"] == 50
    assert event["goal_count"] == 10
    assert event["stickers"] == []
    assert event["completed_at"] is None


def test_the_board_lists_the_cards_in_the_order_they_were_made(client: TestClient, home: Home) -> None:
    _create(client, home, title="はみがき")
    _create(client, home, title="しゅくだい")

    board = client.get(_events_path(home.ledger), headers=home.headers)

    assert board.status_code == 200, board.text
    body = board.json()
    assert body["display_name"] == "たろう"
    assert body["can_modify"] is True
    assert [event["title"] for event in body["events"]] == ["はみがき", "しゅくだい"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " ", "reward_points": 10, "goal_count": 3},
        {"title": "はみがき", "reward_points": 0, "goal_count": 3},
        {"title": "はみがき", "reward_points": -10, "goal_count": 3},
        {"title": "はみがき", "reward_points": 10, "goal_count": 0},
        {"title": "はみがき", "reward_points": 10, "goal_count": 51},
        {"title": "あ" * 101, "reward_points": 10, "goal_count": 3},
    ],
)
def test_a_card_that_cannot_be_filled_or_gives_nothing_is_refused(
    client: TestClient, home: Home, payload: dict[str, Any]
) -> None:
    response = client.post(_events_path(home.ledger), headers=home.headers, json=payload)

    assert response.status_code == 422


# --- シール --------------------------------------------------------------------


def test_each_achievement_sticks_one_sticker(client: TestClient, home: Home) -> None:
    event = _create(client, home, goal_count=3)

    first = _stick(client, home, event, number=1)
    second = _stick(client, home, event, number=2)

    assert [sticker["number"] for sticker in first["stickers"]] == [1]
    assert [sticker["number"] for sticker in second["stickers"]] == [1, 2]
    assert second["completed_at"] is None
    # まだ埋まっていないので台帳は動かない
    assert _ledger(client, home)["balance"] == 0


def test_filling_the_last_square_adds_the_reward_once(client: TestClient, home: Home) -> None:
    event = _create(client, home, title="はみがき", reward_points=50, goal_count=2)
    _stick(client, home, event, number=1)

    completed = _stick(client, home, event, number=2)

    assert completed["completed_at"] is not None
    ledger = _ledger(client, home)
    assert ledger["balance"] == 50
    [entry] = ledger["transactions"]
    assert entry["reason"] == "はみがき"
    assert entry["amount"] == 50
    assert entry["granted_by"] == "おとうさん"


def test_sending_the_same_sticker_twice_sticks_it_once(client: TestClient, home: Home) -> None:
    """二重タップ・再送で 2 枚にならない（番号が冪等の鍵になる）。"""
    event = _create(client, home, goal_count=2)

    _stick(client, home, event, number=1)
    again = _stick(client, home, event, number=1)

    assert [sticker["number"] for sticker in again["stickers"]] == [1]


def test_resending_the_last_sticker_does_not_pay_twice(client: TestClient, home: Home) -> None:
    event = _create(client, home, reward_points=30, goal_count=1)

    _stick(client, home, event, number=1)
    again = _stick(client, home, event, number=1)

    assert again["completed_at"] is not None
    assert _ledger(client, home)["balance"] == 30


def test_skipping_a_number_is_refused(client: TestClient, home: Home) -> None:
    """画面が古い姿を見ている。読み直せば次の番号が分かる。"""
    event = _create(client, home, goal_count=3)

    response = client.put(_sticker_path(home, event, 2), headers=home.headers)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "sticker_out_of_order"


def test_a_full_card_takes_no_more_stickers(client: TestClient, home: Home) -> None:
    event = _create(client, home, goal_count=1)
    _stick(client, home, event, number=1)

    response = client.put(_sticker_path(home, event, 2), headers=home.headers)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "reward_event_already_completed"


# --- はがす --------------------------------------------------------------------


def test_the_last_sticker_can_be_peeled_off(client: TestClient, home: Home) -> None:
    """押し間違いを戻す。"""
    event = _create(client, home, goal_count=3)
    _stick(client, home, event, number=1)
    _stick(client, home, event, number=2)

    response = client.delete(_sticker_path(home, event, 2), headers=home.headers)

    assert response.status_code == 200, response.text
    assert [sticker["number"] for sticker in response.json()["stickers"]] == [1]


def test_only_the_last_sticker_can_be_peeled_off(client: TestClient, home: Home) -> None:
    event = _create(client, home, goal_count=3)
    _stick(client, home, event, number=1)
    _stick(client, home, event, number=2)

    response = client.delete(_sticker_path(home, event, 1), headers=home.headers)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "sticker_out_of_order"


def test_peeling_a_sticker_that_is_already_gone_succeeds(client: TestClient, home: Home) -> None:
    event = _create(client, home, goal_count=3)

    response = client.delete(_sticker_path(home, event, 1), headers=home.headers)

    assert response.status_code == 200, response.text
    assert response.json()["stickers"] == []


def test_a_completed_card_cannot_be_peeled(client: TestClient, home: Home) -> None:
    """ポイントはもう台帳に入っている。戻したいときは台帳の記録を取り消す。"""
    event = _create(client, home, goal_count=1)
    _stick(client, home, event, number=1)

    response = client.delete(_sticker_path(home, event, 1), headers=home.headers)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "reward_event_already_completed"


# --- 消す ----------------------------------------------------------------------


def test_deleting_a_completed_card_keeps_the_points(client: TestClient, home: Home) -> None:
    event = _create(client, home, reward_points=40, goal_count=1)
    _stick(client, home, event, number=1)

    response = client.delete(f"{_events_path(home.ledger)}/{event['id']}", headers=home.headers)

    assert response.status_code == 204
    assert client.get(_events_path(home.ledger), headers=home.headers).json()["events"] == []
    assert _ledger(client, home)["balance"] == 40


def test_deleting_a_card_that_is_already_gone_succeeds(client: TestClient, home: Home) -> None:
    response = client.delete(f"{_events_path(home.ledger)}/999999", headers=home.headers)

    assert response.status_code == 204


# --- 届く範囲 ------------------------------------------------------------------


def test_a_child_sees_their_own_cards_but_cannot_stick(client: TestClient, home: Home) -> None:
    """貼ると台帳にポイントが入るので、貼れるのは記録できる人（親）だけ。"""
    event = _create(client, home, goal_count=2)
    child_headers = _child_headers(client, home)

    board = client.get(_events_path(home.ledger), headers=child_headers)
    stick = client.put(_sticker_path(home, event, 1), headers=child_headers)
    create = client.post(
        _events_path(home.ledger),
        headers=child_headers,
        json={"title": "じぶんで", "reward_points": 1000, "goal_count": 1},
    )

    assert board.status_code == 200, board.text
    assert board.json()["can_modify"] is False
    assert [card["title"] for card in board.json()["events"]] == ["はみがき"]
    assert stick.status_code == 403
    assert create.status_code == 403


def test_a_card_on_another_ledger_is_not_found(client: TestClient, home: Home) -> None:
    event = _create(client, home)
    sibling = add_child(client, home.headers, home.ledger.family_id, display_name="はなこ")
    theirs = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(sibling["ledger_id"])))

    response = client.put(f"{_events_path(theirs)}/{event['id']}/stickers/1", headers=home.headers)

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "reward_event_not_found"


def test_another_familys_cards_are_out_of_reach(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    _create(client, home)
    outsider = create_account(client, admin_headers, username="mom", role="member")
    create_family(client, outsider.headers, name="よその家")

    response = client.get(_events_path(home.ledger), headers=outsider.headers)

    assert response.status_code == 403


def test_removing_the_child_takes_the_cards_with_them(client: TestClient, home: Home) -> None:
    """記録の無い子は消せる。カードとシールは台帳と一緒に消える。"""
    event = _create(client, home, goal_count=3)
    _stick(client, home, event, number=1)

    removed = client.delete(
        f"/api/families/{home.ledger.family_id}/memberships/{home.child_membership_id}", headers=home.headers
    )

    assert removed.status_code == 204, removed.text
    assert client.get(_events_path(home.ledger), headers=home.headers).status_code == 404


def test_independence_takes_completed_cards_with_the_ledger(client: TestClient, home: Home) -> None:
    """独立では台帳の行が先に消える。達成の行を指すカードが消す順を妨げない。"""
    event = _create(client, home, goal_count=1)
    _stick(client, home, event, number=1)
    child_headers = _child_headers(client, home)
    proposed = client.post(
        f"/api/families/{home.ledger.family_id}/memberships/{home.child_membership_id}/independence-proposal",
        headers=home.headers,
    )
    assert proposed.status_code in {200, 201}, proposed.text

    approved = client.post(f"/api/families/{home.ledger.family_id}/independence", headers=child_headers)

    assert approved.status_code == 204, approved.text
    assert client.get(_events_path(home.ledger), headers=home.headers).status_code == 404
