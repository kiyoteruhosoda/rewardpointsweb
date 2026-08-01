from fastapi.testclient import TestClient


def test_admin_users_require_permission(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/admin/users").status_code == 401


def test_user_crud_and_role_scope(client: TestClient, admin_headers: dict[str, str]) -> None:
    # 作成
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "member",
            "email": "member@example.com",
            "display_name": "むすこ",
            "password": "member-pass-1",
            "roles": ["member"],
        },
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    assert response.json()["roles"] == ["member"]
    assert response.json()["display_name"] == "むすこ"

    # member ロールでは items 閲覧のみ・管理系は 403
    login = client.post(
        "/api/auth/login",
        json={"username": "member", "password": "member-pass-1"},
    )
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/items", headers=member_headers).status_code == 200
    assert client.post("/api/items", headers=member_headers, json={"name": "x"}).status_code == 403
    assert client.get("/api/admin/users", headers=member_headers).status_code == 403

    # 更新（無効化）
    response = client.put(
        f"/api/admin/users/{user_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # 削除
    assert client.delete(f"/api/admin/users/{user_id}", headers=admin_headers).status_code == 204
    users = client.get("/api/admin/users", headers=admin_headers).json()
    assert all(u["id"] != user_id for u in users)


def test_duplicate_email_rejected(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "dup",
            "email": "admin@example.com",
            "display_name": "dup",
            "password": "whatever-123",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "email_already_exists"


def test_duplicate_username_rejected(client: TestClient, admin_headers: dict[str, str]) -> None:
    from shared.domain.auth import master_data

    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": master_data.DEFAULT_ADMIN_USERNAME,
            "display_name": "dup",
            "password": "whatever-123",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "username_already_taken"


def test_account_without_email_can_be_created(client: TestClient, admin_headers: dict[str, str]) -> None:
    """子アカウントはメールアドレスを持たない（ADR-0011）。"""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "display_name": "こども", "password": "kid-pass-123", "roles": ["member"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["email"] is None
    assert client.post("/api/auth/login", json={"username": "kid", "password": "kid-pass-123"}).status_code == 200


def test_unknown_role_rejected(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "xyz",
            "email": "x@example.com",
            "display_name": "x",
            "password": "whatever-123",
            "roles": ["nonexistent"],
        },
    )
    assert response.status_code == 400
