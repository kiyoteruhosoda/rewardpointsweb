"""想定外の例外が、フロントエンドの読めるエラーコードとして返ることの検証。

ハンドラが無いと Starlette は text/plain の ``Internal Server Error`` を返す。
API クライアントは本文を JSON として読むので、その場合コードを取り出せず
``unknown_error`` としか表示できない（原因の切り分けもできない）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from presentation.fastapi.error_handling import INTERNAL_ERROR_CODE


@pytest.fixture
def client_with_failing_endpoint(app: FastAPI) -> TestClient:
    @app.get("/api/test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    # 例外を送出させずに応答を確かめる（本番の ASGI サーバーと同じ扱い）。
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_a_json_error_code(client_with_failing_endpoint: TestClient) -> None:
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]["error"] == INTERNAL_ERROR_CODE


def test_unhandled_exception_does_not_leak_the_exception_text(client_with_failing_endpoint: TestClient) -> None:
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert "boom" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_exception_carries_the_request_id(client_with_failing_endpoint: TestClient) -> None:
    """ログの該当行を引けるよう、応答にも requestId を載せる。"""
    response = client_with_failing_endpoint.get("/api/test/boom")

    assert response.headers.get("X-Request-Id")
