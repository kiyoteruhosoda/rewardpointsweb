"""Writing logs to the DB must not collide with the request's transaction.

Uses a **file-backed SQLite**. The shared fixtures' in-memory DB + ``StaticPool``
makes everyone share a single connection, so lock contention never happens and this bug
cannot be reproduced (it does happen with the production default ``sqlite:///app.db``).

Shape of the bug (ADR-0012): writing from a separate connection mid-request collides with the
write lock held by a request that has already run ``db.flush()``, waits out the busy timeout (5 s), then fails.
**The operation succeeds but its record is lost** -- and each line costs a 5-second wait.
For any API that writes, every log line emitted after that point (admin operation records, access log)
falls into this.
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
import shared.infrastructure.models  # noqa: F401 — registers metadata
from shared.domain.auth import master_data
from shared.infrastructure.master_data_seeder import seed_master_data
from shared.kernel.database import db as db_module
from shared.kernel.database.db import Base
from shared.kernel.settings.settings import settings

# A write from a separate connection that gets stuck waits until the busy timeout (5 s by default).
# If a single request takes longer than this, it is waiting on the lock.
_SLOW_REQUEST_SECONDS = 3.0


@pytest.fixture
def file_engine(tmp_path: Path) -> Iterator[sa.Engine]:
    """File-backed SQLite that does not share a connection."""
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
    """App with DB log writes enabled.

    The shared test environment turns off writes to the ``log`` table with ``TESTING=1``
    (so log rows do not pile up on every test). This module looks at **that write path
    itself**, so it is enabled only here.

    ``setup_logging`` replaces the root logger, so restore it during teardown. Otherwise
    later tests keep a handler that writes to an already-disposed engine.

    **The test client's own httpx2 logs ("HTTP Request: ...") are not sent to the DB.**
    Since Starlette 1.10, TestClient returns as soon as the response head arrives while the app keeps running.
    httpx2 emits its line at that point, so it is a direct write from outside the request (a context with no buffer),
    and it collides with the app still holding the write lock and waits 5 s. It is a client-side line that does not
    exist in production, and what we want to see are the app's lines, so only this logger is silenced.
    """
    from presentation.fastapi.app import create_app

    monkeypatch.setenv("TESTING", "0")
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    client_logger = logging.getLogger("httpx2")
    original_client_level = client_logger.level
    client_logger.setLevel(logging.WARNING)
    try:
        with TestClient(create_app()) as client:
            yield client
    finally:
        root.handlers = original_handlers
        client_logger.setLevel(original_client_level)


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
    """A record emitted after ``db.flush()`` is stored and is not slowed down by lock waits."""
    started = time.perf_counter()
    created = file_client.post(
        "/api/admin/users",
        json={"username": "locked-user", "password": "password123", "display_name": "Locked", "roles": []},
        headers=file_admin_headers,
    )
    elapsed = time.perf_counter() - started

    assert created.status_code == 201, created.text
    assert elapsed < _SLOW_REQUEST_SECONDS, f"log write is waiting on the lock ({elapsed:.1f} s)"
    user_id = created.json()["id"]
    assert f"admin_user_created: user_id={user_id}" in _messages(file_engine, "admin_user_created%")


def test_the_access_log_line_is_stored(
    file_client: TestClient, file_admin_headers: dict[str, str], file_engine: sa.Engine
) -> None:
    """The access log (one line per request) is stored too.

    This is why the batched write sits **outside** the request logging. Inside it,
    the access log line would not make it into the buffer in time.
    """
    assert file_client.get("/info").status_code == 200

    with file_engine.connect() as connection:
        stored = list(connection.execute(sa.text("SELECT path, status_code FROM log WHERE logger = 'app.request'")))
    assert ("/info", 200) in [(row[0], row[1]) for row in stored]


def test_the_error_code_reaches_the_log_table(file_client: TestClient, file_engine: sa.Engine) -> None:
    """A failure record reaches the DB together with "what happened".

    Only the column fields go into the ``log`` table; the rest of ``extra`` only appears in
    the stdout JSON. That is why the error code is also put in the message -- if it cannot be
    read from the admin screen (`/admin/logs`), recording it is pointless.
    """
    assert file_client.get("/api/admin/users", headers={"Authorization": "Bearer nope"}).status_code == 401

    assert "request_failed: invalid_token" in _messages(file_engine, "request_failed%")


def test_a_failed_login_is_stored(file_client: TestClient, file_engine: sa.Engine) -> None:
    """A failed login is stored even when the request is rolled back with a 401."""
    assert file_client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"}).status_code == 401

    assert "login_failed: invalid_credentials" in _messages(file_engine, "login_failed%")
