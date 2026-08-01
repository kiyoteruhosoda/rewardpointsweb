"""アカウント削除にパスワード再設定トークンが追随することの検証。

``password_reset_tokens.user_id`` の外部キーに ``ON DELETE CASCADE`` が無いと、
再設定を一度でも申請したアカウントの削除が本番（MariaDB）で外部キーに阻まれて
失敗する。開発用 SQLite は既定で外部キーを検査しないため、ここでは PRAGMA を
有効にしたうえでマイグレーション済みスキーマの挙動を確かめる。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine


@pytest.fixture
def migrated_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = tmp_path / "cascade.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URI", url)
    command.upgrade(Config("alembic.ini"), "head")
    return url


def test_deleting_a_user_removes_their_reset_tokens(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("PRAGMA foreign_keys=ON"))
            connection.execute(
                sa.text(
                    "INSERT INTO users"
                    " (id, username, display_name, password_hash, is_active,"
                    "  must_change_password, created_at, updated_at)"
                    " VALUES (9001, 'taro', 'taro', 'x', 1, 0,"
                    "  '2026-08-01 00:00:00', '2026-08-01 00:00:00')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO password_reset_tokens"
                    " (id, user_id, token_hash, expires_at, created_at)"
                    " VALUES (9001, 9001, 'hash', '2026-08-02 00:00:00', '2026-08-01 00:00:00')"
                )
            )
            connection.execute(sa.text("DELETE FROM users WHERE id = 9001"))
            remaining = connection.execute(
                sa.text("SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = 9001")
            ).scalar_one()
        assert remaining == 0
    finally:
        engine.dispose()
