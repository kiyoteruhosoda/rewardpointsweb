"""想定外の例外が、フロントエンドの読めるエラーコードとして返ることの検証。

ハンドラが無いと Starlette は text/plain の ``Internal Server Error`` を返す。
API クライアントは本文を JSON として読むので、その場合コードを取り出せず
``unknown_error`` としか表示できない（原因の切り分けもできない）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from presentation.fastapi.error_handling import INTERNAL_ERROR_CODE

_ALLOWED_ORIGIN = "https://app.example.com"


def _add_failing_endpoint(app: FastAPI) -> None:
    @app.get("/api/test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")


@pytest.fixture
def client_with_failing_endpoint(app: FastAPI) -> TestClient:
    _add_failing_endpoint(app)
    # 例外を送出させずに応答を確かめる（本番の ASGI サーバーと同じ扱い）。
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def cors_client_with_failing_endpoint(
    engine: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """別オリジンのフロントエンドを許可した構成でアプリを組み立てる。"""
    from presentation.fastapi.app import create_app

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", f'["{_ALLOWED_ORIGIN}"]')
    app = create_app()
    _add_failing_endpoint(app)
    yield TestClient(app, raise_server_exceptions=False)


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


def test_cross_origin_client_can_read_the_error_code(cors_client_with_failing_endpoint: TestClient) -> None:
    """別オリジンからでも本文を読めるよう、500 応答にも CORS ヘッダーを付ける。

    ``Exception`` ハンドラは CORS ミドルウェアの外側に載るため、そこだけに頼ると
    ``Access-Control-Allow-Origin`` が付かない。ブラウザは本文を捨て、画面は
    ``unknown_error`` へ戻ってしまう（受け皿を足した意味が無くなる）。
    """
    response = cors_client_with_failing_endpoint.get("/api/test/boom", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == INTERNAL_ERROR_CODE
    assert response.headers.get("access-control-allow-origin") == _ALLOWED_ORIGIN


def test_failed_request_is_recorded_in_the_access_log(
    client_with_failing_endpoint: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """500 もアクセスログに残す。例外が記録層を素通りすると 500 だけ抜け落ちる。"""
    with caplog.at_level(logging.INFO, logger="app.request"):
        client_with_failing_endpoint.get("/api/test/boom")

    statuses = [getattr(record, "status_code", None) for record in caplog.records if record.name == "app.request"]
    assert 500 in statuses
