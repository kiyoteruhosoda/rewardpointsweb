"""家族・参加者・招待の出力 DTO。

``role`` はドメインの列挙をそのまま載せる。文字列へ落とすと Presentation 層で
``Literal["owner", "parent", "child"]`` へ戻す変換が必要になり、型検査が効かなく
なる。JSON へは列挙の値（``"owner"`` 等）が出る。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class FamilySummaryDTO:
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    member_count: int


@dataclass(frozen=True, kw_only=True)
class MembershipDTO:
    id: int
    display_name: str
    role: FamilyRole
    # アカウント未紐付けの参加者は、招待コードを渡すまでログインできない
    is_linked: bool
    is_me: bool
    username: str | None
    # 台帳を持つのは role = child だけ
    ledger_id: int | None
    balance: int | None
    # 独立が指示され、子本人の承認待ちか（ADR-0014）
    independence_proposed: bool = False
    # 見ている人がこの参加者に対して行える操作。画面はこれだけを見て操作を出す
    # （台帳の ``can_modify`` と同じ考え方 — 押してから断られる操作を出さない）。
    # 既定はすべて偽。参加者 1 人を作って返すだけの応答（子の追加・独立の指示）は
    # 家族全体を読み直さないので、可否を答えられる立場にない。
    can_reset_password: bool = False
    can_graduate: bool = False
    can_remove: bool = False


@dataclass(frozen=True, kw_only=True)
class FamilyDetailDTO:
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    memberships: tuple[MembershipDTO, ...]


@dataclass(frozen=True, kw_only=True)
class InvitationDTO:
    id: int
    role: FamilyRole
    target_membership_id: int | None
    target_display_name: str | None
    expires_at: datetime
    # 平文のコードは発行の応答でだけ載る（保存はハッシュのみ）
    code: str | None


@dataclass(frozen=True, kw_only=True)
class TemporaryPasswordDTO:
    membership_id: int
    username: str
    password: str
    expires_at: datetime
    # 発行の事実をログへ残すために返す（応答本文には載せない）
    issued_by_membership_id: int


@dataclass(frozen=True, kw_only=True)
class RedeemedInvitationDTO:
    family_id: int
    family_name: str
    membership_id: int
    role: FamilyRole
    username: str


__all__ = [
    "FamilyDetailDTO",
    "FamilySummaryDTO",
    "InvitationDTO",
    "MembershipDTO",
    "RedeemedInvitationDTO",
    "TemporaryPasswordDTO",
]
