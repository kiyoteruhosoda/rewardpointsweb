"""Migrating existing accounts' identifiers (ADR-0011).

When ``users.username`` becomes the sign-in identifier, existing rows get **the email address value**.
This rule keeps the sign-in procedure the same before and after the migration;
if it breaks, everyone is locked out.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash

from shared.domain.auth import master_data
from shared.kernel.database import db as db_module

# The revision just before identifiers are split (at this point ``username`` is the display name)
_BEFORE_SPLIT = "default_admin_password"

_EXISTING_PASSWORD = "existing-pass-123"


@pytest.fixture
def migrated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sa.Engine]:
    """Seed one pre-migration row, then upgrade to head."""
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URI", f"sqlite:///{db_path}")
    config = Config("alembic.ini")
    command.upgrade(config, _BEFORE_SPLIT)

    engine = create_engine(f"sqlite:///{db_path}")
    users = sa.table(
        "users",
        sa.column("id"),
        sa.column("email"),
        sa.column("username"),
        sa.column("password_hash"),
        sa.column("is_active"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    now = datetime(2026, 7, 31, 0, 0, 0)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                id=100,
                email="Parent@Example.com",
                # Before the migration ``username`` is the display name (not an identifier)
                username="おかあさん",
                password_hash=generate_password_hash(_EXISTING_PASSWORD),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )

    command.upgrade(config, "head")
    yield engine
    engine.dispose()


def test_existing_account_keeps_its_email_as_the_identifier(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as connection:
        row = connection.execute(sa.text("SELECT username, email, display_name FROM users WHERE id = 100")).one()

    username, email, display_name = row
    # The identifier is the email address value (normalized to lowercase)
    assert username == "parent@example.com"
    assert email == "Parent@Example.com"
    # The previous ``username`` remains as the display name
    assert display_name == "おかあさん"


def test_default_admin_matches_the_master_data(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as connection:
        username: str = connection.execute(
            sa.text("SELECT username FROM users WHERE id = :id"),
            {"id": master_data.DEFAULT_ADMIN_ID},
        ).scalar_one()

    assert username == master_data.DEFAULT_ADMIN_USERNAME


def test_migrated_account_signs_in_with_the_same_credentials(migrated_engine: sa.Engine) -> None:
    """Sign-in works with the same string and the same password as before the migration."""
    from presentation.fastapi.app import create_app

    db_module.set_engine(migrated_engine)
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/auth/login",
                json={"username": "Parent@Example.com", "password": _EXISTING_PASSWORD},
            )
            assert response.status_code == 200, response.text
            assert response.json()["access_token"]
    finally:
        db_module.set_engine(None)
