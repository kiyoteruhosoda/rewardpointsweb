"""利用者（``users``）への窓口の SQLAlchemy 実装。

``shared`` の ``User`` モデルへ触れるのはここだけで、ID 連携の Domain / Application
層はこの実装を知らない。

**作るのは、初めての相手の口座だけ**（ADR-0041）。形は管理画面で作るときの既定に揃える。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)
from shared.infrastructure.models import Role, User

logger = logging.getLogger(__name__)

#: ``users.display_name`` の桁数。⚠ **長い名乗りは切る。** MySQL は厳格モードで
#: 溢れた値を通さないので、切らないと**写しの更新でログインが落ちる**。
_DISPLAY_NAME_LIMIT = 100

#: 作る口座のロール。⚠ **管理画面で作るときの既定と同じ親（``member``）**（ADR-0018）。
#: 家族にはまだ属さず、家族を作るか、招待を受けて加わる。
_ROLE_FOR_NEW_ACCOUNT = "member"


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

    def find_by_username(self, username: str) -> FederatedAccount | None:
        return _as_account(self.session.scalar(select(User).where(User.username == username)))

    def provision(self, *, username: str, email: str | None, display_name: str) -> FederatedAccount | None:
        """初めての相手の口座を作る（ADR-0041）。

        ⚠ **一意の列がぶつかったら ``None``。** 確かめてから作るまでのあいだに、同じ相手の
        往復がもう 1 本戻ることがある。巻き戻すのは作りかけの 1 行だけにしたいので、
        セーブポイントの中で書く（外側の往復の控えは消費済みのまま残す）。
        """
        roles = list(self.session.scalars(select(Role).where(Role.name == _ROLE_FOR_NEW_ACCOUNT)))
        user = User(
            username=username,
            email=email,
            display_name=display_name[:_DISPLAY_NAME_LIMIT],
            # ⚠ **NULL は「ローカルのパスワードが無い」**（ADR-0034）。入り口は IdP だけ。
            password_hash=None,
            is_active=True,
        )
        try:
            with self.session.begin_nested():
                user.roles = roles
                self.session.add(user)
                self.session.flush()
        except IntegrityError:
            return None
        return _as_account(user)

    def refresh_profile(self, user_id: int, *, email: str | None, display_name: str) -> None:
        """名乗りとメールアドレスを写しへ上書きする（ADR-0038）。

        ⚠ **ぶつかる値は書かない。** ``users.email`` は一意なので、別の利用者が
        既に持っている値をそのまま書くと**ログインが 500 で落ちる**。写しの更新で
        ログインを壊すのは本末転倒なので、その項目だけ見送って記録に残す。

        ⚠ **``username`` は触らない。** こちらはログインの識別子で、IdP の名乗りでは
        ない（ADR-0011）。書き換えると、パスワードで入っていた人の入り口が消える。
        """
        user = self.session.get(User, user_id)
        if user is None:  # pragma: no cover - 直前に引けた利用者が消えた場合のみ
            return
        if email is not None and email != user.email and self._email_is_free(email, user_id):
            user.email = email
        name = display_name[:_DISPLAY_NAME_LIMIT]
        if name and name != user.display_name:
            user.display_name = name
        self.session.flush()

    def _email_is_free(self, email: str, user_id: int) -> bool:
        taken = self.session.scalar(select(User.id).where(User.email == email).where(User.id != user_id))
        if taken is not None:
            # ⚠ 値そのものは残さない（PII）。どの項目が見送られたかだけ分かればよい。
            logger.warning("federated_profile_conflict", extra={"field": "email"})
            return False
        return True


def _as_account(user: User | None) -> FederatedAccount | None:
    return None if user is None else FederatedAccount(user_id=user.id, is_active=user.is_active)


__all__ = ["SqlFederatedUserDirectory"]
