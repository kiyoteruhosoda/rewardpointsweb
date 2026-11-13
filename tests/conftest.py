"""Shared test fixtures (SQLite in-memory with master data seeded)."""

from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

import bounded_contexts.account_security.infrastructure.account_security_models
import bounded_contexts.display_devices.infrastructure.display_devices_models
import bounded_contexts.example.infrastructure.item_model
import bounded_contexts.identity_federation.infrastructure.identity_federation_models
import bounded_contexts.reward_points.infrastructure.reward_points_models  # noqa: F401 — registers metadata
import shared.infrastructure.models  # noqa: F401 — registers metadata
from bounded_contexts.email_sender.domain.email_message import EmailMessage
from bounded_contexts.email_sender.infrastructure.smtp_email_sender import SmtpEmailSender
from shared.domain.auth import master_data
from shared.infrastructure.master_data_seeder import seed_master_data
from shared.kernel.database import db as db_module
from shared.kernel.database.db import Base
from shared.kernel.settings.settings import settings


@pytest.fixture
def engine() -> Iterator[sa.Engine]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not check foreign keys by default. Production (MariaDB / InnoDB) does, so
    # without enabling it a defect like "the parent can be deleted while still referenced" passes the tests.
    @sa.event.listens_for(engine, "connect")
    def _enforce_foreign_keys(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
def db_session(engine: sa.Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def app(engine: sa.Engine) -> FastAPI:
    from presentation.fastapi.app import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mail_outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Enable mail sending and capture the messages that were sent.

    ``MAIL_ENABLED`` is off by default, so a test that does not use this is verifying the
    "cannot send" setup. Whenever you want to check a path that is meant to send mail,
    always take this fixture.
    """
    sent: list[EmailMessage] = []
    monkeypatch.setenv("MAIL_ENABLED", "true")
    monkeypatch.setattr(
        SmtpEmailSender,
        "send",
        lambda _self, message: sent.append(message),
    )
    monkeypatch.setattr(SmtpEmailSender, "check_reachable", lambda _self: None)
    return sent


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": master_data.DEFAULT_ADMIN_USERNAME, "password": master_data.DEFAULT_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
