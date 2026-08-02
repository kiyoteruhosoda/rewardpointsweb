from fastapi.testclient import TestClient

from shared.kernel.settings.settings import settings


def test_config_requires_permission(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/admin/config").status_code == 401


def test_get_config_returns_definitions(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/admin/config", headers=admin_headers)
    assert response.status_code == 200
    items = {item["key"]: item for item in response.json()}
    assert "MAIL_SERVER" in items
    assert items["MAIL_SERVER"]["env_locked"] is False
    # secret 項目は値をそのまま返さない
    assert items["MAIL_PASSWORD"]["value"] in (None, "", "********")


def test_save_config_overrides_default(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={"values": {"MAIL_SERVER": "smtp.custom.example"}},
    )
    assert response.status_code == 200

    # settings オブジェクト経由で即時反映される（環境変数 > DB > デフォルト）
    assert settings.mail_server == "smtp.custom.example"

    items = {i["key"]: i for i in client.get("/api/admin/config", headers=admin_headers).json()}
    assert items["MAIL_SERVER"]["value"] == "smtp.custom.example"
    assert items["MAIL_SERVER"]["stored"] is True

    # null で DB 上書きを削除しデフォルトへ戻す
    client.put("/api/admin/config", headers=admin_headers, json={"values": {"MAIL_SERVER": None}})
    assert settings.mail_server == "smtp.example.com"


def test_unknown_key_is_ignored(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={"values": {"DATABASE_URI": "sqlite:///evil.db"}},
    )
    assert response.status_code == 200
    items = {i["key"] for i in client.get("/api/admin/config", headers=admin_headers).json()}
    assert "DATABASE_URI" not in items


def test_rejects_relying_party_id_that_does_not_match_origin(client: TestClient, admin_headers: dict[str, str]) -> None:
    """RP ID とオリジンが噛み合わない組み合わせは保存させない。

    保存できてしまうと、失敗するのは設定画面ではなくパスキーを登録しようと
    した利用者の画面（ブラウザが ``SecurityError`` で拒む）になる。
    """
    response = client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={
            "values": {
                "WEBAUTHN_RP_ID": "rewardpointsweb",
                "WEBAUTHN_ORIGIN": "https://rewardpointsweb.com",
            }
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_webauthn_rp_id"

    # 拒んだ保存は DB に残さない（既定のままであること）
    items = {i["key"]: i for i in client.get("/api/admin/config", headers=admin_headers).json()}
    assert items["WEBAUTHN_RP_ID"]["stored"] is False
    assert settings.webauthn_rp_id == "localhost"


def test_rejects_origin_without_scheme(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={"values": {"WEBAUTHN_RP_ID": "example.com", "WEBAUTHN_ORIGIN": "example.com"}},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_webauthn_origin"


def test_accepts_matching_relying_party_configuration(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={
            "values": {
                "WEBAUTHN_RP_ID": "rewardpointsweb.com",
                "WEBAUTHN_ORIGIN": "https://rewardpointsweb.com",
            }
        },
    )
    assert response.status_code == 200
    assert settings.webauthn_rp_id == "rewardpointsweb.com"

    client.put(
        "/api/admin/config",
        headers=admin_headers,
        json={"values": {"WEBAUTHN_RP_ID": None, "WEBAUTHN_ORIGIN": None}},
    )
    assert settings.webauthn_rp_id == "localhost"
