"""Re-resolve role assignments in a way that survives role renames (0010_realign_roles / ADR-0018).

Operators can rename roles with ``PUT /api/admin/roles/{role_id}``. If the migration looked up
roles by name, in a renamed environment it would not find them, and both the grant changes and the
reassignment would be silently skipped. Passing the migration while "permissions look changed but are not"
is the worst outcome, so this checks that roles are looked up by id (the stable key in ``ROLES``).
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

# The revision just before roles are realigned
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
    """Revert to the grants as they were just before this revision.

    The migration chain uses the **current** source of truth for the 0007 seed, so upgrading as is
    would give ``member`` / ``guest`` the new scopes without waiting for 0010. That would make it
    impossible to check "whether 0010 granted them", so strip them first.
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
    """Build an environment where an operator renamed every role from the admin screen."""
    with engine.begin() as connection:
        for name, role_id in _ROLE_IDS.items():
            connection.execute(
                sa.text("UPDATE roles SET name = :renamed WHERE id = :id"),
                {"renamed": f"{name}-を改名した", "id": role_id},
            )


@pytest.fixture
def renamed_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sa.Engine:
    """Prepare a renamed environment up to just before the migration, then upgrade to head."""
    db_path = tmp_path / "renamed.db"
    monkeypatch.setenv("DATABASE_URI", f"sqlite:///{db_path}")
    config = Config("alembic.ini")
    command.upgrade(config, _BEFORE_REALIGN)

    engine = create_engine(f"sqlite:///{db_path}")
    # Before this revision, parents had the manager role
    _add_account(engine, user_id=100, username="dad", role_id=_ROLE_IDS["manager"])
    # Revert to the state before 0010 grants them (so the granted side can be verified too)
    _revoke(engine, role_id=_ROLE_IDS["member"], codes=("family:manage", "point:manage"))
    _revoke(engine, role_id=_ROLE_IDS["guest"], codes=("family:view", "point:view"))
    _rename_every_builtin_role(engine)

    command.upgrade(config, "head")
    return engine


def test_renamed_admin_still_loses_the_family_scopes(renamed_deployment: sa.Engine) -> None:
    """If not revoked, the system admin keeps being able to reach families and ledgers."""
    scopes = _scopes_of_role_id(renamed_deployment, _ROLE_IDS["admin"])
    assert not scopes & {"family:view", "family:manage", "point:view", "point:manage"}
    # Only the name changed, so the system permissions remain
    assert "user:manage" in scopes


def test_renamed_manager_still_loses_the_family_scopes(renamed_deployment: sa.Engine) -> None:
    scopes = _scopes_of_role_id(renamed_deployment, _ROLE_IDS["manager"])
    assert not scopes & {"family:view", "family:manage", "point:view", "point:manage"}


def test_renamed_member_and_guest_still_gain_their_scopes(renamed_deployment: sa.Engine) -> None:
    """The grants on the receiving side, parents (member) and children (guest), are not skipped by renames either."""
    assert {"family:manage", "point:manage"} <= _scopes_of_role_id(renamed_deployment, _ROLE_IDS["member"])
    assert {"family:view", "point:view"} <= _scopes_of_role_id(renamed_deployment, _ROLE_IDS["guest"])


def test_manager_holders_are_still_reassigned_to_member(renamed_deployment: sa.Engine) -> None:
    """Reassignment does not rely on names either. Skipping it would leave parents unable to touch their family."""
    roles = _role_ids_of_user(renamed_deployment, 100)
    assert roles == {_ROLE_IDS["member"]}
