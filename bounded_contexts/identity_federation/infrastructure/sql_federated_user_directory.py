"""利用者（``users``）への窓口の SQLAlchemy 実装。

``shared`` の ``User`` モデルへ触れるのはここだけで、ID 連携の Domain / Application
層はこの実装を知らない。

**利用者を作る操作は持たない。** SSO は既に居る人の入り口で、アカウントを増やす
経路ではない（ADR-0029）。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)
from shared.infrastructure.models import User


@dataclass(frozen=True)
class SqlFederatedUserDirectory:
    session: Session

    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        return _as_account(self.session.get(User, user_id))

    def find_by_email(self, email: str) -> FederatedAccount | None:
        """メールアドレスで引く。

        ``users.email`` は任意項目で NULL があり得る（ADR-0011）。SQL の比較では
        NULL はどの値とも等しくならないため、メールアドレスを持たない利用者
        （子ども）がここへ当たることはない。空文字は照合そのものを行わない
        ——空の ``email`` 列を持つ利用者と噛み合わせないため。
        """
        if not email:
            return None
        return _as_account(self.session.scalar(select(User).where(User.email == email)))


def _as_account(user: User | None) -> FederatedAccount | None:
    return None if user is None else FederatedAccount(user_id=user.id, is_active=user.is_active)


__all__ = ["SqlFederatedUserDirectory"]
