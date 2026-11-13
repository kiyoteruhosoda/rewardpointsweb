"""The DB-touching part of the endpoint that creates an account for a first-time user (ADR-0041).

⚠ The case of **being overtaken between checking and creating** is handled by the unique constraint.
The use case unit tests swap out the roster, so this is the only place it can be checked.
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
    # ⚠ Long names are truncated to the column length (MySQL strict mode rejects overflowing values)
    assert len(user.display_name) == 100


def test_a_value_taken_in_the_meantime_returns_none_and_keeps_the_session_usable(db_session: Session) -> None:
    """⚠ Only the half-created row is rolled back. Outer changes (consuming the round-trip record etc.) remain."""
    db_session.add(User(username="taken", email=None, display_name="先客", password_hash=None))
    db_session.flush()
    directory = SqlFederatedUserDirectory(db_session)

    duplicated = directory.provision(username="taken", email=None, display_name="後から")

    assert duplicated is None
    db_session.commit()
    names = db_session.scalars(sa.select(User.display_name).where(User.username == "taken")).all()
    assert names == ["先客"]
