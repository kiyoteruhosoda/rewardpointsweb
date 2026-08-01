"""ロールの改名に耐えて割り当てを引き直す（0010_realign_roles / ADR-0018）。

ロールの名前は ``PUT /api/admin/roles/{role_id}`` で運用者が変えられる。移行が
名前でロールを引くと、改名された環境では対象が見つからず、付与の増減も割り当ての
引き直しも黙って飛ばされる。「権限を変えたつもりで変わっていない」状態のまま
移行が通るのが一番たちが悪いので、id（``ROLES`` の安定キー）で引くことを確かめる。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash

from shared.domain.auth import master_data

# ロールを揃え直す直前のリビジョン
_BEFORE_REALIGN = "password_reset_cascade"

_ROLE_IDS = {name: role_id for role_id, name in master_data.ROLES}


def _scopes_of_role_id(engine: sa.Engine, role_id: int) -> set[str]:
    query = sa.text(
        "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id WHERE rp.role_id = :role"
    )
    with engine.connect() as connection:
        return {str(code) for (code,) in connection.execute(query, {"role": role_id}).all()}


def _role_ids_of_user(engine: sa.Engine, user_id: int) -> set[int]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT role_id FROM user_roles WHERE user_id = :user"), {"user": user_id}
        ).all()
    return {int(str(role_id)) for (role_id,) in rows}


def _add_account(engine: sa.Engine, *, user_id: int, username: str, role_id: int) -> None:
    now = datetime(2026, 8, 1, 0, 0, 0)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users"
                " (id, email, username, display_name, password_hash, is_active, created_at, updated_at)"
                " VALUES (:id, NULL, :username, :username, :password_hash, 1, :now, :now)"
            ),
            {"id": user_id, "username": username, "password_hash": generate_password_hash("pass-123"), "now": now},
        )
        connection.execute(
            sa.text("INSERT INTO user_roles (user_id, role_id) VALUES (:user, :role)"),
            {"user": user_id, "role": role_id},
        )


def _revoke(engine: sa.Engine, *, role_id: int, codes: tuple[str, ...]) -> None:
    """このリビジョン直前の付与の姿へ戻す。

    移行の連鎖は 0007 の投入に**現在の**正本を使うため、そのまま上げると
    ``member`` / ``guest`` は 0010 を待たずに新しい scope を持ってしまう。それでは
    「0010 が付与したのか」を確かめられないので、先に剥がしておく。
    """
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE role_id = :role AND permission_id IN"
                " (SELECT id FROM permissions WHERE code IN :codes)"
            ).bindparams(sa.bindparam("codes", expanding=True)),
            {"role": role_id, "codes": list(codes)},
        )


def _rename_every_builtin_role(engine: sa.Engine) -> None:
    """運用者が管理画面から全ロールを改名した環境を作る。"""
    with engine.begin() as connection:
        for name, role_id in _ROLE_IDS.items():
            connection.execute(
                sa.text("UPDATE roles SET name = :renamed WHERE id = :id"),
                {"renamed": f"{name}-を改名した", "id": role_id},
            )


@pytest.fixture
def renamed_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sa.Engine:
    """改名済みの環境を移行前まで用意し、head まで上げる。"""
    db_path = tmp_path / "renamed.db"
    monkeypatch.setenv("DATABASE_URI", f"sqlite:///{db_path}")
    config = Config("alembic.ini")
    command.upgrade(config, _BEFORE_REALIGN)

    engine = create_engine(f"sqlite:///{db_path}")
    # このリビジョン以前、親は manager ロールだった
    _add_account(engine, user_id=100, username="dad", role_id=_ROLE_IDS["manager"])
    # 0010 が付与する前の姿へ戻す（付与された側も検証できるようにする）
    _revoke(engine, role_id=_ROLE_IDS["member"], codes=("family:manage", "point:manage"))
    _revoke(engine, role_id=_ROLE_IDS["guest"], codes=("family:view", "point:view"))
    _rename_every_builtin_role(engine)

    command.upgrade(config, "head")
    return engine


def test_renamed_admin_still_loses_the_family_scopes(renamed_deployment: sa.Engine) -> None:
    """取り上げそこねると、システム管理者が家族と台帳へ手を伸ばせるままになる。"""
    scopes = _scopes_of_role_id(renamed_deployment, _ROLE_IDS["admin"])
    assert not scopes & {"family:view", "family:manage", "point:view", "point:manage"}
    # 名前を変えただけなので、システム系の権限は残る
    assert "user:manage" in scopes


def test_renamed_manager_still_loses_the_family_scopes(renamed_deployment: sa.Engine) -> None:
    scopes = _scopes_of_role_id(renamed_deployment, _ROLE_IDS["manager"])
    assert not scopes & {"family:view", "family:manage", "point:view", "point:manage"}


def test_renamed_member_and_guest_still_gain_their_scopes(renamed_deployment: sa.Engine) -> None:
    """親（member）と子（guest）が受け取る側の付与も、改名で飛ばされない。"""
    assert {"family:manage", "point:manage"} <= _scopes_of_role_id(renamed_deployment, _ROLE_IDS["member"])
    assert {"family:view", "point:view"} <= _scopes_of_role_id(renamed_deployment, _ROLE_IDS["guest"])


def test_manager_holders_are_still_reassigned_to_member(renamed_deployment: sa.Engine) -> None:
    """割り当ての引き直しも名前に頼らない。飛ばすと親が家族を触れなくなる。"""
    roles = _role_ids_of_user(renamed_deployment, 100)
    assert roles == {_ROLE_IDS["member"]}
