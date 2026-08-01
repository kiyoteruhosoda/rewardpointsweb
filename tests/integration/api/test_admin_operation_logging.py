"""管理操作とログインの失敗がアプリログへ残ること。

このプロジェクトには監査ログ（`audit_log`）が無く、`log` テーブルだけが「いつ何が
起きたか」の記録になる。アカウント・ロール・システム設定を変える操作と、失敗した
ログインは、後から必ず問われる出来事なので残す。

**識別子は本文に入れる。** `log` テーブルへ入るのは列にある項目
（`message` / `path` / `method` / `status_code` / `trace`）だけで、`extra` の残りは
stdout の JSON にしか出ない。管理画面（`/admin/logs`）から読めなければ意味がない。
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


def _messages(caplog: pytest.LogCaptureFixture, logger_prefix: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name.startswith(logger_prefix)]


def test_creating_a_user_is_logged_with_its_id(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.users"):
        created = client.post(
            "/api/admin/users",
            json={"username": "logged-user", "password": "password123", "display_name": "Logged", "roles": []},
            headers=admin_headers,
        )

    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert f"admin_user_created: user_id={user_id}" in _messages(caplog, "presentation.fastapi.routers.admin.users")


def test_updating_a_user_logs_the_changed_field_names_only(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """変えた項目の名前だけを残す。値（表示名・パスワード）は残さない。"""
    created = client.post(
        "/api/admin/users",
        json={"username": "updated-user", "password": "password123", "display_name": "Before", "roles": []},
        headers=admin_headers,
    )
    user_id = created.json()["id"]

    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.users"):
        updated = client.put(
            f"/api/admin/users/{user_id}",
            json={"display_name": "After", "is_active": False},
            headers=admin_headers,
        )

    assert updated.status_code == 200, updated.text
    messages = _messages(caplog, "presentation.fastapi.routers.admin.users")
    assert f"admin_user_updated: user_id={user_id} fields=display_name,is_active" in messages
    assert not any("After" in message for message in messages)


def test_deleting_a_user_is_logged(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    created = client.post(
        "/api/admin/users",
        json={"username": "deleted-user", "password": "password123", "display_name": "Doomed", "roles": []},
        headers=admin_headers,
    )
    user_id = created.json()["id"]

    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.users"):
        assert client.delete(f"/api/admin/users/{user_id}", headers=admin_headers).status_code == 204

    assert f"admin_user_deleted: user_id={user_id}" in _messages(caplog, "presentation.fastapi.routers.admin.users")


def test_changing_a_role_logs_the_resulting_permissions(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """権限は「変わった後の姿」を残す（差分だけでは当時の状態を組み立て直せない）。"""
    created = client.post(
        "/api/admin/roles",
        json={"name": "auditor", "permissions": []},
        headers=admin_headers,
    )
    role_id = created.json()["id"]

    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.roles"):
        updated = client.put(
            f"/api/admin/roles/{role_id}",
            json={"permissions": ["log:view"]},
            headers=admin_headers,
        )

    assert updated.status_code == 200, updated.text
    messages = _messages(caplog, "presentation.fastapi.routers.admin.roles")
    assert f"admin_role_updated: role_id={role_id} name=auditor permissions=log:view" in messages


def test_saving_system_settings_logs_the_keys_but_not_the_values(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """値には秘匿項目（``MAIL_PASSWORD`` 等）が入るので、キー名だけを残す。"""
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.config"):
        saved = client.put(
            "/api/admin/config",
            json={"values": {"MAIL_PASSWORD": "s3cret", "LOG_LEVEL": "INFO"}},
            headers=admin_headers,
        )

    assert saved.status_code == 200, saved.text
    messages = _messages(caplog, "presentation.fastapi.routers.admin.config")
    assert "system_settings_updated: keys=LOG_LEVEL,MAIL_PASSWORD" in messages
    assert not any("s3cret" in message for message in messages)


def test_saving_an_unknown_key_is_not_recorded_as_a_change(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """採り込まなかったキーは記録しない。

    ``SystemSettingService.save()`` は未知のキーと、伏せ字のまま送り返された秘匿
    項目を黙って捨てる。要求されたキーをそのまま残すと、何も変えていない保存が
    「設定を変更した」として残ってしまう。
    """
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.config"):
        saved = client.put(
            "/api/admin/config",
            json={"values": {"UNKNOWN_KEY": "x", "LOG_LEVEL": "INFO"}},
            headers=admin_headers,
        )

    assert saved.status_code == 200, saved.text
    messages = _messages(caplog, "presentation.fastapi.routers.admin.config")
    assert "system_settings_updated: keys=LOG_LEVEL" in messages
    assert not any("UNKNOWN_KEY" in message for message in messages)


def test_saving_only_an_unchanged_secret_records_nothing_changed(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """伏せ字のまま送り返された秘匿項目だけの保存は「変更なし」と残る。"""
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.config"):
        saved = client.put(
            "/api/admin/config",
            json={"values": {"MAIL_PASSWORD": "********"}},
            headers=admin_headers,
        )

    assert saved.status_code == 200, saved.text
    assert "system_settings_updated: keys=none" in _messages(caplog, "presentation.fastapi.routers.admin.config")


def test_a_failed_passkey_login_is_logged_as_a_warning(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """パスキーのログイン失敗も、パスワードと同じく WARNING で残る。"""
    logger_name = "bounded_contexts.account_security.presentation.passkey_login_router"
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        response = client.post(
            "/api/auth/passkey/login",
            json={"challenge_id": "does-not-exist", "credential": {}},
        )

    assert response.status_code in (400, 401), response.text
    records = [record for record in caplog.records if record.name == logger_name]
    assert [record.levelno for record in records] == [logging.WARNING]
    assert records[0].getMessage().startswith("passkey_login_failed: ")


def test_a_failed_login_is_logged_as_a_warning(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """試行が続いていないかを運用で見たいので、401 の既定（INFO）より上げる。"""
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.auth"):
        assert client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"}).status_code == 401

    records = [record for record in caplog.records if record.name == "presentation.fastapi.routers.auth"]
    assert [record.levelno for record in records] == [logging.WARNING]
    assert records[0].getMessage() == "login_failed: invalid_credentials"
    # ユーザー名は残さない（CLAUDE.md「ログ」）
    assert "nobody" not in records[0].getMessage()
