"""reward_points コンテキストの Pydantic スキーマ。

長さ・上限はドメインの値オブジェクトの定数を使う（同じ数字を書き写さない）。
``role`` はドメインの列挙をそのまま使い、JSON へは値（``"owner"`` 等）が出る。
OpenAPI にも列挙として現れる。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from bounded_contexts.reward_points.domain.value_objects.display_name import (
    MAX_LENGTH as DISPLAY_NAME_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.family_name import MAX_LENGTH as FAMILY_NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    MAX_LENGTH as IDEMPOTENCY_KEY_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_MAGNITUDE as AMOUNT_MAX
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import (
    MAX_LENGTH as REASON_MAX_LENGTH,
)
from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH


def _non_blank(value: str) -> str:
    """前後の空白を落とし、空白だけの入力を弾く。

    ``min_length=1`` は空白 1 文字を通してしまうため、表示される値は落としてから
    長さを見る。
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _non_zero(value: int) -> int:
    """0 は台帳に意味を持たない（``CHECK (amount <> 0)``。ADR-0010）。"""
    if value == 0:
        raise ValueError("must not be zero")
    return value


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]
DisplayNameStr = Annotated[NonBlankStr, Field(max_length=DISPLAY_NAME_MAX_LENGTH)]
CodeStr = Annotated[NonBlankStr, Field(max_length=64)]


# --- 家族 --------------------------------------------------------------------


class FamilyCreateRequest(BaseModel):
    name: Annotated[NonBlankStr, Field(max_length=FAMILY_NAME_MAX_LENGTH)]
    # 家族の中での自分の呼び名。省略時はアカウントの表示名を使う
    display_name: DisplayNameStr | None = None


class MembershipResponse(BaseModel):
    id: int
    display_name: str
    role: FamilyRole
    is_linked: bool
    is_me: bool
    username: str | None
    ledger_id: int | None
    balance: int | None
    # 独立が指示され、子本人の承認待ちか（ADR-0014）
    independence_proposed: bool


class FamilySummaryResponse(BaseModel):
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    member_count: int


class FamilyDetailResponse(BaseModel):
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    memberships: list[MembershipResponse]


class FamilyRenameRequest(BaseModel):
    name: Annotated[NonBlankStr, Field(max_length=FAMILY_NAME_MAX_LENGTH)]


class ChildCreateRequest(BaseModel):
    display_name: DisplayNameStr


# --- 招待 --------------------------------------------------------------------


class InvitationCreateRequest(BaseModel):
    role: FamilyRole
    # role = child の招待では、親が先に作った参加者を必ず指す（ADR-0011）
    target_membership_id: int | None = None


class InvitationResponse(BaseModel):
    id: int
    role: FamilyRole
    target_membership_id: int | None
    target_display_name: str | None
    expires_at: datetime
    # 平文のコードは発行の応答でだけ載る（保存はハッシュのみ）
    code: str | None


class InvitationAcceptRequest(BaseModel):
    code: CodeStr
    # 参加者を指していない招待（親として加わる場合）でのみ必要
    display_name: DisplayNameStr | None = None


class InvitationRedeemRequest(BaseModel):
    """未認証で呼ぶ。招待コードと引き換えにアカウントを作る（ADR-0011）。"""

    code: CodeStr
    username: Annotated[str, Field(min_length=1, max_length=USERNAME_MAX_LENGTH)]
    password: Annotated[str, Field(min_length=8)]
    display_name: DisplayNameStr | None = None


class RedeemedInvitationResponse(BaseModel):
    family_id: int
    family_name: str
    membership_id: int
    role: FamilyRole
    username: str


class TemporaryPasswordResponse(BaseModel):
    membership_id: int
    username: str
    password: str
    expires_at: datetime


# --- 台帳 --------------------------------------------------------------------


class TransactionCreateRequest(BaseModel):
    # 符号で加算（正）と消費（負）を表す
    amount: Annotated[int, Field(ge=-AMOUNT_MAX, le=AMOUNT_MAX), AfterValidator(_non_zero)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    idempotency_key: Annotated[NonBlankStr, Field(max_length=IDEMPOTENCY_KEY_MAX_LENGTH)]
    # 未指定なら受け付けた時刻（UTC）
    occurred_at: datetime | None = None


class ReversalCreateRequest(BaseModel):
    idempotency_key: Annotated[NonBlankStr, Field(max_length=IDEMPOTENCY_KEY_MAX_LENGTH)]


class TransactionResponse(BaseModel):
    id: int
    amount: int
    reason: str
    occurred_at: datetime
    created_at: datetime
    reversal_of_id: int | None
    is_reversed: bool
    granted_by: str | None


class LedgerResponse(BaseModel):
    ledger_id: int
    family_id: int
    membership_id: int
    display_name: str
    balance: int
    can_modify: bool
    transactions: list[TransactionResponse]


__all__ = [
    "ChildCreateRequest",
    "FamilyCreateRequest",
    "FamilyDetailResponse",
    "FamilyRenameRequest",
    "FamilySummaryResponse",
    "InvitationAcceptRequest",
    "InvitationCreateRequest",
    "InvitationRedeemRequest",
    "InvitationResponse",
    "LedgerResponse",
    "MembershipResponse",
    "NonBlankStr",
    "RedeemedInvitationResponse",
    "ReversalCreateRequest",
    "TemporaryPasswordResponse",
    "TransactionCreateRequest",
    "TransactionResponse",
]
