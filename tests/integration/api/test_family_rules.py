"""家族のルール（家族で決めた約束ごと。ADR-0027）。

書けるのは親（owner / parent）で、読めるのは家族の全員。子は自分の台帳の画面で
同じ文面を読むので、家族の詳細に載ることまでを確かめる。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bounded_contexts.reward_points.domain.value_objects.family_rules import MAX_LENGTH
from tests.integration.api.family_support import (
    Account,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)

Json = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class Home:
    """owner と、同じ家族の親・子。

    どのテストも「誰かがこの家族のルールを書こうとする」から始まるので 1 つに
    まとめる（引数を 3 つに収める意味もある。ADR-0016）。
    """

    client: TestClient
    family_id: int
    owner: Account
    parent: Account
    child_headers: dict[str, str]

    def write(self, headers: dict[str, str], rules: str | None) -> Any:
        return self.client.put(f"/api/families/{self.family_id}/rules", headers=headers, json={"rules": rules})

    def view(self, headers: dict[str, str]) -> Json:
        response = self.client.get(f"/api/families/{self.family_id}", headers=headers)
        assert response.status_code == 200, response.text
        detail: Json = response.json()
        return detail


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    dad = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    mom = create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")
    family_id = create_family(client, dad.headers)

    invitation = issue_invitation(client, dad.headers, family_id, role="parent")
    accepted = client.post(
        "/api/families/invitations/accept",
        headers=mom.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )
    assert accepted.status_code == 200, accepted.text

    child = add_child(client, dad.headers, family_id, display_name="たろう")
    for_child = issue_invitation(
        client, dad.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": for_child["code"], "username": "taro", "password": "taro-pass-123", "display_name": "たろう"},
    )
    assert redeemed.status_code == 201, redeemed.text

    return Home(
        client=client,
        family_id=family_id,
        owner=dad,
        parent=mom,
        child_headers=login(client, username="taro", password="taro-pass-123"),
    )


def test_a_family_starts_without_rules(home: Home) -> None:
    assert home.view(home.owner.headers)["rules"] is None


def test_the_owner_writes_the_rules(home: Home) -> None:
    response = home.write(home.owner.headers, "おてつだい 10 pt\nしゅくだい 20 pt")

    assert response.status_code == 200, response.text
    assert response.json()["rules"] == "おてつだい 10 pt\nしゅくだい 20 pt"
    assert home.view(home.owner.headers)["rules"] == "おてつだい 10 pt\nしゅくだい 20 pt"


def test_a_parent_writes_the_rules_too(home: Home) -> None:
    """改名（owner のみ）と違い、日々の決めごとは親なら書ける（ADR-0027）。"""
    assert home.write(home.parent.headers, "ゲームは 1 日 1 時間").status_code == 200


def test_writing_again_replaces_what_was_there(home: Home) -> None:
    home.write(home.owner.headers, "さいしょ")

    assert home.write(home.owner.headers, "あとから").json()["rules"] == "あとから"


def test_an_empty_body_clears_the_rules(home: Home) -> None:
    """空白だけの入力は「消す」と同じ。読めない文字だけのルールを残さない。"""
    home.write(home.owner.headers, "きえるはず")

    assert home.write(home.owner.headers, "   ").json()["rules"] is None
    assert home.write(home.owner.headers, None).json()["rules"] is None


def test_the_child_reads_the_rules_but_cannot_write_them(home: Home) -> None:
    """読むのは全員。書き換えるのは親だけ（子の画面には入り口が出ない）。"""
    home.write(home.owner.headers, "おかたづけ 10 pt")

    assert home.view(home.child_headers)["rules"] == "おかたづけ 10 pt"
    denied = home.write(home.child_headers, "ぜんぶ 100 pt")
    # 子のアカウントは family:manage を持たない（ADR-0018）
    assert denied.status_code == 403
    assert home.view(home.owner.headers)["rules"] == "おかたづけ 10 pt"


def test_someone_outside_the_family_cannot_write_the_rules(
    home: Home, client: TestClient, admin_headers: dict[str, str]
) -> None:
    outsider = create_account(client, admin_headers, username="aunt", role="member", display_name="おば")

    denied = home.write(outsider.headers, "よそのルール")

    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "family_access_denied"


def test_rules_longer_than_the_limit_are_refused(home: Home) -> None:
    assert home.write(home.owner.headers, "あ" * (MAX_LENGTH + 1)).status_code == 422
    assert home.write(home.owner.headers, "あ" * MAX_LENGTH).status_code == 200
