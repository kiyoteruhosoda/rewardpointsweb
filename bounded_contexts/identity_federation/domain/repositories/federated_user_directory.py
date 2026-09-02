"""利用者（``users``）への窓口。

ID 連携から見ると、利用者を引くのは「外の仕組み」に当たる。Domain 層が SQLAlchemy
のモデルへ触れないよう、必要な操作だけをここで宣言し、実装（Infrastructure 層）が
``shared`` のモデルへ橋渡しする。

**作る操作は置かない。** SSO は既に居る利用者への入り口で、アカウントを増やす経路
ではない（``domain/value_objects/account_linking_policy.py``）。
"""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)


class FederatedUserDirectory(Protocol):
    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        """利用者を内部 ID で引く。無ければ ``None``。"""

    def find_by_email(self, email: str) -> FederatedAccount | None:
        """利用者をメールアドレスで引く（初回の結び付けの手掛かり）。

        メールアドレスは任意項目なので、持っていない利用者は決して当たらない
        （ADR-0011）。
        """


__all__ = ["FederatedUserDirectory"]
