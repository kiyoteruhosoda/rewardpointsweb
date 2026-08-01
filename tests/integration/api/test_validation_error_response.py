"""入力検証の失敗（422）が、画面の読める形で返ることの検証。

FastAPI 既定の ``{"detail": [...]}`` は配列で、SPA の ``extractErrorCode``
（``frontend/src/services/api.ts``）が当てはめられない。どの項目が悪くても
``unknown_error`` の文言にしかならず、利用者は直しようがない。加えて既定の
本文には ``input`` として送った値がそのまま乗る（打ち込んだパスワードを
含む）。ここでは形とコード、そして**値が出ないこと**を固定する。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from presentation.fastapi.error_handling import VALIDATION_ERROR_CODE

# 8 文字未満で弾かれる。既定の応答ならこの値が ``input`` に乗って返る。
_PASSWORD = "secret"


def test_validation_failure_uses_the_same_error_shape_as_other_failures(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "display_name": "こども", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["password"]}}


def test_the_response_never_echoes_what_was_sent(client: TestClient, admin_headers: dict[str, str]) -> None:
    """項目名だけを返す。``input`` が乗るとパスワードとメールアドレスが外へ出る。"""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "kid", "email": "kid@invalid", "display_name": "こども", "password": _PASSWORD},
    )

    assert response.status_code == 422
    body = response.text
    assert _PASSWORD not in body
    assert "kid@invalid" not in body
    assert response.json()["detail"]["fields"] == ["email", "password"]


def test_missing_body_is_reported_without_a_field_name(client: TestClient, admin_headers: dict[str, str]) -> None:
    """本文そのものが無い場合も同じ形で返す（項目名は ``body``）。"""
    response = client.post("/api/admin/users", headers=admin_headers)

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["body"]}}


def test_account_signup_reports_the_field_that_failed(client: TestClient) -> None:
    """招待コードでのアカウント作成（未認証）も同じ形で返る。"""
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": "ABCDE12345", "username": "kid", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"error": VALIDATION_ERROR_CODE, "fields": ["password"]}}
