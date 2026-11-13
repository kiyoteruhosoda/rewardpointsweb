"""Admin operations and failed sign-ins are recorded in the app log.

This project has no audit log (`audit_log`); the `log` table is the only record of "when
what happened". Operations that change accounts, roles or system settings, and failed
sign-ins, are events that will always be asked about later, so they are recorded.

**Put identifiers in the message body.** Only the items that are columns go into the `log` table
(`message` / `path` / `method` / `status_code` / `trace`); the rest of `extra` only goes
to the stdout JSON. It is useless if it cannot be read from the admin screen (`/admin/logs`).
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
    """Record only the names of the changed items. Do not record values (display name, password)."""
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
    """Record permissions "as they are after the change" (a diff alone cannot rebuild the state at the time)."""
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
    """Values include secret items (``MAIL_PASSWORD`` etc.), so record only the key names."""
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
    """Keys that were not taken in are not recorded.

    ``SystemSettingService.save()`` silently drops unknown keys and secret items sent back
    still masked. Recording the requested keys as is would log a save that changed nothing
    as "settings changed".
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
    """A save containing only secret items sent back still masked is recorded as "no change"."""
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.admin.config"):
        saved = client.put(
            "/api/admin/config",
            json={"values": {"MAIL_PASSWORD": "********"}},
            headers=admin_headers,
        )

    assert saved.status_code == 200, saved.text
    assert "system_settings_updated: keys=none" in _messages(caplog, "presentation.fastapi.routers.admin.config")


def test_a_failed_passkey_login_is_logged_as_a_warning(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Failed passkey sign-ins are also recorded at WARNING, like passwords."""
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
    """Ops wants to see whether attempts keep coming, so raise it above the 401 default (INFO)."""
    with caplog.at_level(logging.DEBUG, logger="presentation.fastapi.routers.auth"):
        assert client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"}).status_code == 401

    records = [record for record in caplog.records if record.name == "presentation.fastapi.routers.auth"]
    assert [record.levelno for record in records] == [logging.WARNING]
    assert records[0].getMessage() == "login_failed: invalid_credentials"
    # Do not record the username (CLAUDE.md "Logs")
    assert "nobody" not in records[0].getMessage()
