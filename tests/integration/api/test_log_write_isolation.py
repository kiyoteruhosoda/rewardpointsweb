"""ログの DB 書き込みが、リクエストのトランザクションと衝突しないこと。

**ファイル実体の SQLite** を使う。共通フィクスチャの in-memory + ``StaticPool`` は
全員が 1 本のコネクションを共有するため、ロックの競合が起きず、この不具合を
再現できない（実運用の既定 ``sqlite:///app.db`` では起きる）。

不具合の形（ADR-0012）: 処理の途中で別コネクションから書くと、``db.flush()`` 済みの
リクエストが握った書き込みロックと衝突し、busy timeout（5 秒）待った末に失敗する。
**操作は成功したのに記録だけ残らない**——しかも 1 行につき 5 秒待たされる。
書き込みを行う API では、その後に出るログ行（管理操作の記録・アクセスログ）が
まるごとこれに当たる。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import bounded_contexts.account_security.infrastructure.account_security_models
import bounded_contexts.example.infrastructure.item_model
import bounded_contexts.reward_points.infrastructure.reward_points_models  # noqa: F401
import shared.infrastructure.models  # noqa: F401 — メタデータ登録
from shared.domain.auth import master_data
from shared.infrastructure.master_data_seeder import seed_master_data
from shared.kernel.database import db as db_module
from shared.kernel.database.db import Base
from shared.kernel.settings.settings import settings

# 別コネクションからの書き込みが詰まると busy timeout（既定 5 秒）まで待つ。
# 1 リクエストがこれを超えるようなら、ロックで待たされている。
_SLOW_REQUEST_SECONDS = 3.0


@pytest.fixture
def file_engine(tmp_path: Path) -> Iterator[sa.Engine]:
    """コネクションを共有しない、ファイル実体の SQLite。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'logs.db'}")
    Base.metadata.create_all(engine)
    db_module.set_engine(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_master_data(session)
    session.commit()
    session.close()
    yield engine
    db_module.set_engine(None)
    settings.reload_db_overrides()
    engine.dispose()


@pytest.fixture
def file_client(file_engine: sa.Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """DB へのログ書き込みを有効にしたアプリ。

    共通のテスト環境は ``TESTING=1`` で ``log`` テーブルへの書き込みを切っている
    （テストのたびにログ行が増えないようにするため）。ここは**その書き込み経路
    そのもの**を見るので、このモジュールでだけ有効にする。

    ``setup_logging`` はルートロガーを差し替えるので、後始末で元へ戻す。戻さないと
    後続のテストが、破棄済みのエンジンへ書きに行くハンドラを抱えたままになる。
    """
    from presentation.fastapi.app import create_app

    monkeypatch.setenv("TESTING", "0")
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        with TestClient(create_app()) as client:
            yield client
    finally:
        root.handlers = original_handlers


@pytest.fixture
def file_admin_headers(file_client: TestClient) -> dict[str, str]:
    response = file_client.post(
        "/api/auth/login",
        json={
            "username": master_data.DEFAULT_ADMIN_USERNAME,
            "password": master_data.DEFAULT_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _messages(engine: sa.Engine, like: str) -> list[str]:
    with engine.connect() as connection:
        rows = connection.execute(sa.text("SELECT message FROM log WHERE message LIKE :like"), {"like": like})
        return [str(row[0]) for row in rows]


def test_a_log_line_emitted_after_a_write_is_stored(
    file_client: TestClient, file_admin_headers: dict[str, str], file_engine: sa.Engine
) -> None:
    """``db.flush()`` の後に出た記録が残り、ロック待ちで遅くならないこと。"""
    started = time.perf_counter()
    created = file_client.post(
        "/api/admin/users",
        json={"username": "locked-user", "password": "password123", "display_name": "Locked", "roles": []},
        headers=file_admin_headers,
    )
    elapsed = time.perf_counter() - started

    assert created.status_code == 201, created.text
    assert elapsed < _SLOW_REQUEST_SECONDS, f"ログの書き込みがロックを待っている（{elapsed:.1f} 秒）"
    user_id = created.json()["id"]
    assert f"admin_user_created: user_id={user_id}" in _messages(file_engine, "admin_user_created%")


def test_the_access_log_line_is_stored(
    file_client: TestClient, file_admin_headers: dict[str, str], file_engine: sa.Engine
) -> None:
    """アクセスログ（リクエストごとの 1 行）も残ること。

    まとめ書きをリクエストログの**外側**に置いているのはこのため。内側だと
    アクセスログの行が控えに間に合わない。
    """
    assert file_client.get("/info").status_code == 200

    with file_engine.connect() as connection:
        stored = list(connection.execute(sa.text("SELECT path, status_code FROM log WHERE logger = 'app.request'")))
    assert ("/info", 200) in [(row[0], row[1]) for row in stored]


def test_the_error_code_reaches_the_log_table(file_client: TestClient, file_engine: sa.Engine) -> None:
    """失敗の記録が「何が起きたか」ごと DB に残ること。

    ``log`` テーブルへ入るのは列にある項目だけで、``extra`` の残りは stdout の
    JSON にしか出ない。エラーコードを本文にも入れているのはこのため——管理画面
    （`/admin/logs`）から読めなければ、記録した意味がない。
    """
    assert file_client.get("/api/admin/users", headers={"Authorization": "Bearer nope"}).status_code == 401

    assert "request_failed: invalid_token" in _messages(file_engine, "request_failed%")


def test_a_failed_login_is_stored(file_client: TestClient, file_engine: sa.Engine) -> None:
    """401 でリクエストがロールバックされても、ログインの失敗は残ること。"""
    assert file_client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"}).status_code == 401

    assert "login_failed: invalid_credentials" in _messages(file_engine, "login_failed%")
