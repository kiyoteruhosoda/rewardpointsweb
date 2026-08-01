"""家族の中での立場。

認可の判断はこの列挙が持つ性質だけで行い、呼び出し側に ``role == "owner"`` の
ような比較を書かない（ADR-0009 の認可表がここに 1 か所だけ現れる）。

============ ============ ======== ============ ====== ======
role         家族の管理   子の作成 加算・消費   訂正   閲覧
============ ============ ======== ============ ====== ======
owner        ○            ○        全ての子     ○      全ての子
parent       ×            ○        全ての子     ○      全ての子
child        ×            ×        ×            ×      自分の台帳のみ
============ ============ ======== ============ ====== ======
"""

from __future__ import annotations

from enum import Enum


class FamilyRole(Enum):
    OWNER = "owner"
    PARENT = "parent"
    CHILD = "child"

    @property
    def is_guardian(self) -> bool:
        """親の立場か（owner または parent）。子の台帳を扱えるのはこの 2 つ。"""
        return self in (FamilyRole.OWNER, FamilyRole.PARENT)

    @property
    def can_administer_family(self) -> bool:
        """家族そのもの（名前・参加者の除名）を管理できるか。owner だけ。"""
        return self is FamilyRole.OWNER

    @property
    def has_own_ledger(self) -> bool:
        """ポイント台帳を 1 対 1 で持つ立場か。"""
        return self is FamilyRole.CHILD

    @property
    def is_invitable(self) -> bool:
        """招待コードで配ってよい立場か。

        owner は配れない。配れると、受け取った人が元の owner を除名して家族を
        乗っ取れてしまう（招待の受諾は未認証の経路からも来る）。owner を移す
        必要が生じたら、専用の引き継ぎ操作として設計する。
        """
        return self is not FamilyRole.OWNER


__all__ = ["FamilyRole"]
