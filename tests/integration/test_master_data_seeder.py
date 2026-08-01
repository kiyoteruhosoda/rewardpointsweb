"""初期管理者のパスワードを、どこまで追随させ・どこから触らないかの検証。"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from shared.domain.auth import master_data
from shared.infrastructure.master_data_seeder import reconcile_default_admin, seed_master_data
from shared.infrastructure.models import User


def _session(engine: sa.Engine) -> Session:
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _admin(session: Session) -> User:
    admin = session.scalar(select(User).where(User.email == master_data.DEFAULT_ADMIN_EMAIL))
    assert admin is not None
    return admin


def test_seeded_admin_can_be_authenticated_with_the_documented_password(db_session: Session) -> None:
    assert check_password_hash(_admin(db_session).password_hash, master_data.DEFAULT_ADMIN_PASSWORD)


def test_admin_left_on_a_superseded_default_follows_the_new_default(engine: sa.Engine) -> None:
    """既定値のまま運用されている管理者は、既定値の変更に追随する。"""
    assert master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES, "旧既定値が無いとこの経路を検証できない"
    session = _session(engine)
    _admin(session).password_hash = master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES[-1]
    session.commit()

    assert reconcile_default_admin(session) is True
    session.commit()
    assert check_password_hash(_admin(session).password_hash, master_data.DEFAULT_ADMIN_PASSWORD)
    session.close()


def test_password_chosen_by_the_operator_is_left_alone(engine: sa.Engine) -> None:
    session = _session(engine)
    chosen = generate_password_hash("chosen-by-the-operator")
    _admin(session).password_hash = chosen
    session.commit()

    assert reconcile_default_admin(session) is False
    session.commit()
    assert _admin(session).password_hash == chosen
    session.close()


def test_explicit_reset_restores_the_default_password(engine: sa.Engine) -> None:
    """締め出されたときの復旧経路。明示したときだけ上書きする。"""
    session = _session(engine)
    _admin(session).password_hash = generate_password_hash("forgotten")
    session.commit()

    seed_master_data(session, reset_admin_password=True)
    session.commit()
    assert check_password_hash(_admin(session).password_hash, master_data.DEFAULT_ADMIN_PASSWORD)
    session.close()


def test_explicit_reset_applies_the_configured_password(engine: sa.Engine) -> None:
    session = _session(engine)
    seed_master_data(session, admin_password="from-the-environment", reset_admin_password=True)
    session.commit()

    assert check_password_hash(_admin(session).password_hash, "from-the-environment")
    session.close()


def test_seeding_twice_does_not_duplicate_roles_or_permissions(engine: sa.Engine) -> None:
    session = _session(engine)
    seed_master_data(session)
    session.commit()

    admin = _admin(session)
    assert [role.name for role in admin.roles] == [master_data.DEFAULT_ADMIN_ROLE]
    # admin は家族・ポイントに関与しない（ADR-0018）
    assert admin.permission_codes == frozenset(master_data.ROLE_PERMISSIONS["admin"])
    assert not admin.permission_codes & {"family:view", "family:manage", "point:view", "point:manage"}
    session.close()
