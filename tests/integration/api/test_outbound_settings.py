"""通信先の URL と鍵の場所は環境変数だけで決める（ADR-0056）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shared.kernel.settings.settings import settings
from shared.kernel.settings.system_settings_defaults import ENV_ONLY_SETTINGS


@pytest.mark.parametrize("key", sorted(ENV_ONLY_SETTINGS))
def test_env_only_setting_cannot_be_saved_from_the_screen(
    client: TestClient, admin_headers: dict[str, str], key: str
) -> None:
    response = client.put(
        "/api/admin/config", headers=admin_headers, json={"values": {key: "https://attacker.example"}}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {"error": "setting_env_only", "key": key}
    items = {i["key"]: i for i in client.get("/api/admin/config", headers=admin_headers).json()}
    assert items[key]["env_only"] is True


@pytest.mark.parametrize("key", sorted(ENV_ONLY_SETTINGS))
def test_env_only_setting_ignores_a_value_left_in_the_database(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv(key, "from-env")
    monkeypatch.setattr(settings._db, "get", lambda _key: "left-in-the-database")

    assert settings.resolve(key) == "from-env"


def test_mail_server_inside_the_home_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    for host in ("10.10.2.11", "127.0.0.1", "db", "db.ns.svc.cluster.local", "smtp.local", "https://smtp.example.com"):
        response = client.put("/api/admin/config", headers=admin_headers, json={"values": {"MAIL_SERVER": host}})
        assert response.status_code == 400, host
        assert response.json()["detail"] == {"error": "invalid_destination", "key": "MAIL_SERVER"}
