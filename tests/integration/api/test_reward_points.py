"""ポイント API（メンバー・共有・履歴）。

役割ごとに 3 人のログインアカウントを用意する。

- ``manager_headers`` — メンバーを登録する管理者（所有者）
- ``other_manager_headers`` — 同じ scope を持つが、共有されるまで他人のメンバーは触れない
- ``member_headers`` — メンバー本人。閲覧だけできる（``point:manage`` を持たない）
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

PASSWORD = "password123"
MANAGER_EMAIL = "manager@example.com"
OTHER_MANAGER_EMAIL = "other-manager@example.com"
MEMBER_EMAIL = "kid@example.com"
Headers = dict[str, str]


def _create_user(client: TestClient, admin_headers: Headers, *, email: str, role: str) -> int:
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "email": email,
            "username": email.split("@")[0],
            "password": PASSWORD,
            "roles": [role],
        },
    )
    assert response.status_code == 201, response.text
    user_id: int = response.json()["id"]
    return user_id


def _login(client: TestClient, email: str) -> Headers:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def manager_headers(client: TestClient, admin_headers: Headers) -> Headers:
    _create_user(client, admin_headers, email=MANAGER_EMAIL, role="manager")
    return _login(client, MANAGER_EMAIL)


@pytest.fixture
def other_manager_headers(client: TestClient, admin_headers: Headers) -> Headers:
    _create_user(client, admin_headers, email=OTHER_MANAGER_EMAIL, role="manager")
    return _login(client, OTHER_MANAGER_EMAIL)


@pytest.fixture
def member_user_id(client: TestClient, admin_headers: Headers) -> int:
    return _create_user(client, admin_headers, email=MEMBER_EMAIL, role="member")


@pytest.fixture
def member_headers(client: TestClient, member_user_id: int) -> Headers:
    assert member_user_id
    return _login(client, MEMBER_EMAIL)


def _register_member(client: TestClient, headers: Headers, *, name: str, linked_email: str | None = None) -> int:
    body: dict[str, Any] = {"name": name}
    if linked_email:
        body["linked_user_email"] = linked_email
    response = client.post("/api/members", headers=headers, json=body)
    assert response.status_code == 201, response.text
    member_id: int = response.json()["id"]
    return member_id


def _add_points(client: TestClient, headers: Headers, member_id: int, *, points: int, reason: str = "お手伝い") -> Any:
    return client.post(
        f"/api/members/{member_id}/points/additions",
        headers=headers,
        json={"points": points, "reason": reason},
    )


def _consume_points(client: TestClient, headers: Headers, member_id: int, *, points: int) -> Any:
    return client.post(
        f"/api/members/{member_id}/points/consumptions",
        headers=headers,
        json={"points": points, "application": "おかし"},
    )


# --- 認証・認可 --------------------------------------------------------------


def test_endpoints_require_authentication(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/members").status_code == 401
    assert client.post("/api/members", json={"name": "x"}).status_code == 401
    assert client.get("/api/members/1/points").status_code == 401


# --- メンバーとポイント ------------------------------------------------------


def test_manager_registers_a_member_and_records_points(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")

    assert _add_points(client, manager_headers, member_id, points=100).status_code == 201
    assert _consume_points(client, manager_headers, member_id, points=30).status_code == 201

    ledger = client.get(f"/api/members/{member_id}/points", headers=manager_headers)
    assert ledger.status_code == 200
    body = ledger.json()
    assert body["member_name"] == "ハナ"
    assert body["balance"] == 70
    assert body["access_level"] == "manage"
    assert [entry["signed_points"] for entry in body["entries"]] == [-30, 100]


def test_member_list_shows_the_balance(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=40)

    response = client.get("/api/members", headers=manager_headers)
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": member_id,
            "name": "ハナ",
            "balance": 40,
            "access_level": "manage",
            "is_self": False,
            "is_owner": True,
            "has_linked_user": False,
        }
    ]


def test_blank_name_and_non_positive_points_are_rejected(client: TestClient, manager_headers: Headers) -> None:
    assert client.post("/api/members", headers=manager_headers, json={"name": "   "}).status_code == 422

    member_id = _register_member(client, manager_headers, name="ハナ")
    assert _add_points(client, manager_headers, member_id, points=0).status_code == 422
    assert _add_points(client, manager_headers, member_id, points=-5).status_code == 422
    assert _add_points(client, manager_headers, member_id, points=10, reason="  ").status_code == 422


def test_deleting_a_point_entry_updates_the_balance(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    entry_id = _add_points(client, manager_headers, member_id, points=100).json()["id"]
    _add_points(client, manager_headers, member_id, points=5)

    assert client.delete(f"/api/members/{member_id}/points/{entry_id}", headers=manager_headers).status_code == 204
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["balance"] == 5


def test_a_point_entry_of_another_member_cannot_be_deleted(client: TestClient, manager_headers: Headers) -> None:
    first = _register_member(client, manager_headers, name="ハナ")
    second = _register_member(client, manager_headers, name="タロウ")
    entry_id = _add_points(client, manager_headers, first, points=100).json()["id"]

    response = client.delete(f"/api/members/{second}/points/{entry_id}", headers=manager_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "point_entry_not_found"
    assert client.get(f"/api/members/{first}/points", headers=manager_headers).json()["balance"] == 100


def test_deleting_a_member_removes_its_history(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=100)

    assert client.delete(f"/api/members/{member_id}", headers=manager_headers).status_code == 204
    assert client.get("/api/members", headers=manager_headers).json() == []
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).status_code == 404


# --- メンバー本人（閲覧のみ） ------------------------------------------------


def test_linked_member_sees_own_points_but_cannot_change_them(
    client: TestClient, manager_headers: Headers, member_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ", linked_email=MEMBER_EMAIL)
    _add_points(client, manager_headers, member_id, points=100)
    _consume_points(client, manager_headers, member_id, points=20)

    listed = client.get("/api/members", headers=member_headers)
    assert listed.status_code == 200
    assert [(item["id"], item["access_level"], item["is_self"]) for item in listed.json()] == [
        (member_id, "view", True)
    ]

    ledger = client.get(f"/api/members/{member_id}/points", headers=member_headers)
    assert ledger.status_code == 200
    assert ledger.json()["balance"] == 80
    assert ledger.json()["access_level"] == "view"
    assert len(ledger.json()["entries"]) == 2  # 履歴は見られる

    # scope（``point:manage``）が無いので、加算・消費・削除はできない
    assert _add_points(client, member_headers, member_id, points=10).status_code == 403
    assert _consume_points(client, member_headers, member_id, points=10).status_code == 403
    entry_id = ledger.json()["entries"][0]["id"]
    assert client.delete(f"/api/members/{member_id}/points/{entry_id}", headers=member_headers).status_code == 403
    assert client.delete(f"/api/members/{member_id}", headers=member_headers).status_code == 403


def test_a_member_cannot_see_other_members(
    client: TestClient, manager_headers: Headers, member_headers: Headers
) -> None:
    own = _register_member(client, manager_headers, name="ハナ", linked_email=MEMBER_EMAIL)
    other = _register_member(client, manager_headers, name="タロウ")

    assert [item["id"] for item in client.get("/api/members", headers=member_headers).json()] == [own]
    response = client.get(f"/api/members/{other}/points", headers=member_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "member_not_found"


def test_one_account_cannot_be_linked_to_two_members(
    client: TestClient, manager_headers: Headers, member_user_id: int
) -> None:
    assert member_user_id
    _register_member(client, manager_headers, name="ハナ", linked_email=MEMBER_EMAIL)

    response = client.post(
        "/api/members",
        headers=manager_headers,
        json={"name": "タロウ", "linked_user_email": MEMBER_EMAIL},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "linked_user_already_taken"


def test_linking_an_unknown_address_is_rejected(client: TestClient, manager_headers: Headers) -> None:
    response = client.post(
        "/api/members",
        headers=manager_headers,
        json={"name": "ハナ", "linked_user_email": "nobody@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "share_target_not_found"


# --- 共有 --------------------------------------------------------------------


def test_another_manager_cannot_reach_a_member_until_it_is_shared(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")

    assert client.get("/api/members", headers=other_manager_headers).json() == []
    response = client.get(f"/api/members/{member_id}/points", headers=other_manager_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "member_not_found"
    assert _add_points(client, other_manager_headers, member_id, points=10).status_code == 404


def test_sharing_with_manage_lets_the_other_manager_record_points(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    shared = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    )
    assert shared.status_code == 201
    assert shared.json()["email"] == OTHER_MANAGER_EMAIL

    listed = client.get("/api/members", headers=other_manager_headers).json()
    assert [(item["id"], item["access_level"]) for item in listed] == [(member_id, "manage")]
    assert _add_points(client, other_manager_headers, member_id, points=50).status_code == 201
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["balance"] == 50


def test_sharing_with_view_allows_reading_only(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    """``point:manage`` を持つ相手でも、view で共有されたメンバーは変更できない。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=100)
    client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "view"},
    )

    ledger = client.get(f"/api/members/{member_id}/points", headers=other_manager_headers)
    assert ledger.status_code == 200
    assert ledger.json()["access_level"] == "view"

    response = _add_points(client, other_manager_headers, member_id, points=10)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "member_access_denied"
    assert client.delete(f"/api/members/{member_id}", headers=other_manager_headers).status_code == 403


def test_share_defaults_to_view(client: TestClient, manager_headers: Headers, other_manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    response = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL},
    )

    assert response.status_code == 201
    assert response.json()["access_level"] == "view"


def test_shares_can_be_listed_and_revoked(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    target_user_id = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    ).json()["user_id"]

    listed = client.get(f"/api/members/{member_id}/shares", headers=manager_headers)
    assert listed.status_code == 200
    assert [(item["email"], item["access_level"]) for item in listed.json()] == [(OTHER_MANAGER_EMAIL, "manage")]

    revoked = client.delete(f"/api/members/{member_id}/shares/{target_user_id}", headers=manager_headers)
    assert revoked.status_code == 204
    assert client.get(f"/api/members/{member_id}/shares", headers=manager_headers).json() == []
    assert client.get(f"/api/members/{member_id}/points", headers=other_manager_headers).status_code == 404


def test_revoking_a_share_that_does_not_exist(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")

    response = client.delete(f"/api/members/{member_id}/shares/9999", headers=manager_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "member_share_not_found"


def test_sharing_the_same_account_twice_is_rejected(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    body = {"email": OTHER_MANAGER_EMAIL, "access_level": "manage"}
    assert client.post(f"/api/members/{member_id}/shares", headers=manager_headers, json=body).status_code == 201

    response = client.post(f"/api/members/{member_id}/shares", headers=manager_headers, json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "member_already_shared"


def test_sharing_with_the_owner_is_rejected(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")

    response = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": MANAGER_EMAIL, "access_level": "manage"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "share_with_owner_not_allowed"


def test_sharing_with_an_unknown_address_is_rejected(client: TestClient, manager_headers: Headers) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")

    response = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "share_target_not_found"


@pytest.mark.parametrize("shared_level", ["view", "manage"])
def test_only_the_owner_can_manage_shares(
    client: TestClient,
    manager_headers: Headers,
    other_manager_headers: Headers,
    member_user_id: int,
    shared_level: str,
) -> None:
    """共有された相手は、共有を配り直せない（``manage`` で共有されていても）。

    許すと、所有者の知らないところで共有先が増え、所有者が配った他の共有を取り消す
    こともできてしまう。誰に渡すかを決めるのは所有者だけ。
    """
    assert member_user_id
    member_id = _register_member(client, manager_headers, name="ハナ")
    target_user_id = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": shared_level},
    ).json()["user_id"]

    # 一覧・追加・解除のいずれも所有者以外は拒む
    assert client.get(f"/api/members/{member_id}/shares", headers=other_manager_headers).status_code == 403
    added = client.post(
        f"/api/members/{member_id}/shares",
        headers=other_manager_headers,
        json={"email": MEMBER_EMAIL},
    )
    assert added.status_code == 403
    assert added.json()["detail"]["error"] == "member_access_denied"
    revoked = client.delete(f"/api/members/{member_id}/shares/{target_user_id}", headers=other_manager_headers)
    assert revoked.status_code == 403

    # 所有者から見て共有は 1 件のまま（増えても減ってもいない）
    assert len(client.get(f"/api/members/{member_id}/shares", headers=manager_headers).json()) == 1


def test_a_manage_share_does_not_allow_deleting_the_member(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    """共有先がメンバーと履歴すべてを消せてはいけない。記録と削除は分ける。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=100)
    client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    )

    response = client.delete(f"/api/members/{member_id}", headers=other_manager_headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "member_access_denied"
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["balance"] == 100


def test_shared_manager_sees_is_owner_false(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    )

    shared_view = client.get("/api/members", headers=other_manager_headers).json()
    assert [(item["access_level"], item["is_owner"]) for item in shared_view] == [("manage", False)]
    ledger = client.get(f"/api/members/{member_id}/points", headers=other_manager_headers).json()
    assert ledger["is_owner"] is False
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["is_owner"] is True


def test_a_manage_share_still_allows_recording_points(
    client: TestClient, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    """共有の管理を所有者に限っても、``manage`` 共有先の記録は妨げない。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    )

    assert _add_points(client, other_manager_headers, member_id, points=50).status_code == 201
    assert client.get(f"/api/members/{member_id}/points", headers=other_manager_headers).json()["balance"] == 50


# --- アカウント削除との関係 --------------------------------------------------
#
# 本番（MariaDB）は外部キーを検査するため、参照を残したままアカウントを消すと
# DB が拒む。参照ごとに何が起きるべきかをここで固定する。


def test_deleting_an_account_that_owns_members_is_refused(
    client: TestClient, admin_headers: Headers, manager_headers: Headers
) -> None:
    """メンバーを登録したままのアカウントは消せない（履歴ごと失われるため）。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=100)
    owner_id = client.get("/api/auth/me", headers=manager_headers).json()["user_id"]

    response = client.delete(f"/api/admin/users/{owner_id}", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "user_still_owns_members"

    # 拒んだので、アカウントもメンバーも履歴も残っている
    assert client.get(f"/api/admin/users/{owner_id}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["balance"] == 100


def test_an_account_can_be_deleted_once_its_members_are_gone(
    client: TestClient, admin_headers: Headers, manager_headers: Headers
) -> None:
    member_id = _register_member(client, manager_headers, name="ハナ")
    owner_id = client.get("/api/auth/me", headers=manager_headers).json()["user_id"]
    assert client.delete(f"/api/admin/users/{owner_id}", headers=admin_headers).status_code == 409

    client.delete(f"/api/members/{member_id}", headers=manager_headers)
    assert client.delete(f"/api/admin/users/{owner_id}", headers=admin_headers).status_code == 204


def test_deleting_a_shared_account_removes_only_the_share(
    client: TestClient, admin_headers: Headers, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    """共有先のアカウントを消しても、メンバーと履歴は所有者の側に残る。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    _add_points(client, manager_headers, member_id, points=100)
    shared_user_id = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    ).json()["user_id"]

    assert client.delete(f"/api/admin/users/{shared_user_id}", headers=admin_headers).status_code == 204

    assert client.get(f"/api/members/{member_id}/shares", headers=manager_headers).json() == []
    assert client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()["balance"] == 100


def test_deleting_a_linked_account_keeps_the_member(
    client: TestClient, admin_headers: Headers, manager_headers: Headers, member_user_id: int
) -> None:
    """本人のアカウントを消しても、メンバーは残る（紐付けだけが外れる）。"""
    member_id = _register_member(client, manager_headers, name="ハナ", linked_email=MEMBER_EMAIL)
    _add_points(client, manager_headers, member_id, points=100)

    assert client.delete(f"/api/admin/users/{member_user_id}", headers=admin_headers).status_code == 204

    listed = client.get("/api/members", headers=manager_headers).json()
    assert [(item["id"], item["balance"], item["has_linked_user"]) for item in listed] == [(member_id, 100, False)]


def test_deleting_the_recording_account_keeps_the_history(
    client: TestClient, admin_headers: Headers, manager_headers: Headers, other_manager_headers: Headers
) -> None:
    """記録した人のアカウントを消しても履歴は残る（履歴はメンバーのもの）。"""
    member_id = _register_member(client, manager_headers, name="ハナ")
    recorder_id = client.post(
        f"/api/members/{member_id}/shares",
        headers=manager_headers,
        json={"email": OTHER_MANAGER_EMAIL, "access_level": "manage"},
    ).json()["user_id"]
    _add_points(client, other_manager_headers, member_id, points=60)

    assert client.delete(f"/api/admin/users/{recorder_id}", headers=admin_headers).status_code == 204

    ledger = client.get(f"/api/members/{member_id}/points", headers=manager_headers).json()
    assert ledger["balance"] == 60
    assert [entry["signed_points"] for entry in ledger["entries"]] == [60]
