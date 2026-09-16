"""初めての相手の口座を作る口（ADR-0041）の、DB に触れる部分。

⚠ **確かめてから作るまでのあいだに追い越される**場合を、一意制約の側で受け止める。
ユースケースの単体試験では名簿を差し替えているので、ここでしか確かめられない。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.infrastructure.sql_federated_user_directory import (
    SqlFederatedUserDirectory,
)
from shared.infrastructure.models import User


def test_the_new_account_is_a_parent_without_a_password(db_session: Session) -> None:
    account = SqlFederatedUserDirectory(db_session).provision(
        username="newcomer", email="new@example.com", display_name="新しい親" * 30
    )

    assert account is not None
    user = db_session.get(User, account.user_id)
    assert user is not None
    assert user.password_hash is None
    assert [role.name for role in user.roles] == ["member"]
    # ⚠ 長い名乗りは桁数で切る（MySQL の厳格モードは溢れた値を通さない）
    assert len(user.display_name) == 100


def test_a_value_taken_in_the_meantime_returns_none_and_keeps_the_session_usable(db_session: Session) -> None:
    """⚠ 巻き戻すのは作りかけの 1 行だけ。外側の変更（往復の控えの消費など）は残る。"""
    db_session.add(User(username="taken", email=None, display_name="先客", password_hash=None))
    db_session.flush()
    directory = SqlFederatedUserDirectory(db_session)

    duplicated = directory.provision(username="taken", email=None, display_name="後から")

    assert duplicated is None
    db_session.commit()
    names = db_session.scalars(sa.select(User.display_name).where(User.username == "taken")).all()
    assert names == ["先客"]
