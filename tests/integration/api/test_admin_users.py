from fastapi.testclient import TestClient


def test_admin_users_require_permission(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/admin/users").status_code == 401


def test_user_crud_and_role_scope(client: TestClient, admin_headers: dict[str, str]) -> None:
    # Create
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

    # The member role can only view items; admin endpoints are 403
    login = client.post(
        "/api/auth/login",
        json={"username": "member", "password": "member-pass-1"},
    )
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/items", headers=member_headers).status_code == 200
    assert client.post("/api/items", headers=member_headers, json={"name": "x"}).status_code == 403
    assert client.get("/api/admin/users", headers=member_headers).status_code == 403

    # Update (deactivate)
    response = client.put(
        f"/api/admin/users/{user_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Delete
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
    """Child accounts have no email address (ADR-0011)."""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "display_name": "こども", "password": "kid-pass-123", "roles": ["member"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["email"] is None
    assert client.post("/api/auth/login", json={"username": "kid", "password": "kid-pass-123"}).status_code == 200


def test_roles_can_be_changed_and_effective_scopes_follow(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Changing a user's roles immediately changes what that user can do (scope)."""
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "swappable",
            "display_name": "いれかえ",
            "password": "swap-pass-123",
            "roles": ["guest"],
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert created.json()["permissions"] == sorted(["dashboard:view", "gui:view", "family:view", "point:view"])

    login = client.post("/api/auth/login", json={"username": "swappable", "password": "swap-pass-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/items", headers=headers).status_code == 403

    # A change sends "the whole state after the change", not a diff
    updated = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={"roles": ["guest", "manager"]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["roles"] == ["guest", "manager"]
    assert "item:manage" in updated.json()["permissions"]

    # Already issued tokens carry the old scope, so get a new one before checking
    login = client.post("/api/auth/login", json={"username": "swappable", "password": "swap-pass-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/items", headers=headers).status_code == 200

    # An empty list means "no roles" = no permissions
    cleared = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={"roles": []})
    assert cleared.status_code == 200
    assert cleared.json()["roles"] == []
    assert cleared.json()["permissions"] == []


def test_role_change_keeps_other_fields(client: TestClient, admin_headers: dict[str, str]) -> None:
    """A change that omits ``roles`` does not touch the roles."""
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "kept",
            "display_name": "そのまま",
            "password": "kept-pass-123",
            "roles": ["member"],
        },
    )
    user_id = created.json()["id"]

    response = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={"display_name": "改名"})
    assert response.status_code == 200
    assert response.json()["roles"] == ["member"]
    assert response.json()["display_name"] == "改名"


def test_unknown_role_rejected_on_update(client: TestClient, admin_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "target", "display_name": "t", "password": "target-pass-1", "roles": ["member"]},
    )
    user_id = created.json()["id"]

    response = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={"roles": ["nonexistent"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unknown_roles"
    # A rejected change leaves nothing behind
    assert client.get("/api/admin/users", headers=admin_headers).status_code == 200


def test_cannot_revoke_own_user_manage(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Rejected, because taking the admin scope away from yourself cannot be undone from the screen."""
    me = client.get("/api/auth/me", headers=admin_headers).json()

    response = client.put(f"/api/admin/users/{me['user_id']}", headers=admin_headers, json={"roles": ["guest"]})
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "cannot_revoke_own_user_manage"

    still_admin = client.get("/api/admin/users", headers=admin_headers).json()
    assert [u["roles"] for u in still_admin if u["id"] == me["user_id"]] == [["admin"]]


def test_own_roles_can_change_while_user_manage_remains(client: TestClient, admin_headers: dict[str, str]) -> None:
    """As long as the admin scope remains, adding roles to yourself is not blocked."""
    me = client.get("/api/auth/me", headers=admin_headers).json()

    response = client.put(
        f"/api/admin/users/{me['user_id']}",
        headers=admin_headers,
        json={"roles": ["admin", "member"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["admin", "member"]


def test_other_admin_roles_can_be_revoked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Another user's admin role can be removed (needed for handing over)."""
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "second", "display_name": "副管理", "password": "second-pass-1", "roles": ["admin"]},
    )
    user_id = created.json()["id"]

    response = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={"roles": ["member"]})
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["member"]
    assert "user:manage" not in response.json()["permissions"]


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


def test_a_manager_cannot_read_the_app_logs(client: TestClient, admin_headers: dict[str, str]) -> None:
    """App logs are admin only (task #786)."""
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "email": "log-manager@example.com",
            "username": "logmanager",
            "display_name": "ログの確かめ",
            "password": "password-123",
            "roles": ["manager"],
        },
    )
    assert created.status_code == 201, created.text
    client.cookies.clear()
    signed_in = client.post("/api/auth/login", json={"username": "logmanager", "password": "password-123"})
    assert signed_in.status_code == 200, signed_in.text
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}

    assert "log:view" not in client.get("/api/auth/me", headers=headers).json()["scopes"]
    assert client.get("/api/admin/logs", headers=headers).status_code == 403
