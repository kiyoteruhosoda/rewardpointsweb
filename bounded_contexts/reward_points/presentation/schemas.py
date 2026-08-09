"""reward_points コンテキストの Pydantic スキーマ。

長さ・上限はドメインの値オブジェクトの定数を使う（同じ数字を書き写さない）。
``role`` はドメインの列挙をそのまま使い、JSON へは値（``"owner"`` 等）が出る。
OpenAPI にも列挙として現れる。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from bounded_contexts.reward_points.domain.value_objects.display_name import (
    MAX_LENGTH as DISPLAY_NAME_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.family_name import MAX_LENGTH as FAMILY_NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    MAX_BASE_LENGTH as IDEMPOTENCY_KEY_MAX_BASE_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    MAX_LENGTH as IDEMPOTENCY_KEY_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    STEP_SEPARATOR,
    is_derived,
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


def _not_a_step_key(value: str) -> str:
    """段階ごとに分けた鍵の形（``<鍵>#reversal``）は受け取らない。

    台帳の鍵の空間は 1 つ（``UNIQUE (ledger_id, idempotency_key)``）しかない。
    訂正が内部で作る鍵と同じ形を外から書けると、無関係な記録を「同じ操作の
    再送」と取り違え、打ち消しを書いたつもりで書けていない状態になる。
    """
    if is_derived(value):
        raise ValueError(f"must not contain {STEP_SEPARATOR!r}")
    return value


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]
IdempotencyKeyStr = Annotated[
    NonBlankStr, AfterValidator(_not_a_step_key), Field(max_length=IDEMPOTENCY_KEY_MAX_LENGTH)
]
# 訂正は 1 回で 2 行書き、鍵を段階ごとに分ける。分けた後も列に収まる長さまで
CorrectionKeyStr = Annotated[
    NonBlankStr, AfterValidator(_not_a_step_key), Field(max_length=IDEMPOTENCY_KEY_MAX_BASE_LENGTH)
]
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
    # 見ている人がこの参加者に対して行える操作。画面はこれを見て操作を出す
    can_reset_password: bool
    can_propose_independence: bool
    can_remove: bool


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


class MemberOrderRequest(BaseModel):
    """並べたい順の参加者 ID。その家族の子をちょうど 1 度ずつ並べる。"""

    membership_ids: list[int]


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
    idempotency_key: IdempotencyKeyStr
    # 未指定なら受け付けた時刻（UTC）
    occurred_at: datetime | None = None


class ReversalCreateRequest(BaseModel):
    idempotency_key: IdempotencyKeyStr


class CorrectionCreateRequest(BaseModel):
    """訂正後の内容（ADR-0022）。書き換えではなく、正しい内容を書き直す。"""

    amount: Annotated[int, Field(ge=-AMOUNT_MAX, le=AMOUNT_MAX), AfterValidator(_non_zero)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    idempotency_key: CorrectionKeyStr
    # 未指定なら元の記録の発生日時を引き継ぐ
    occurred_at: datetime | None = None


class TransactionResponse(BaseModel):
    id: int
    amount: int
    reason: str
    occurred_at: datetime
    created_at: datetime
    reversal_of_id: int | None
    # 訂正後のレコードなら、言い直した相手の ID（ADR-0022）
    corrects_id: int | None
    is_reversed: bool
    granted_by: str | None


class CorrectionResponse(BaseModel):
    """1 回の訂正で足された 2 行。元のレコードは履歴に残る。"""

    reversal: TransactionResponse
    correction: TransactionResponse


# --- 毎日のボーナス（ADR-0024） ----------------------------------------------


class DailyBonusRequest(BaseModel):
    """毎日いくつ足すか。加算だけなので符号は持たない（正の数のみ）。"""

    amount: Annotated[int, Field(ge=1, le=AMOUNT_MAX)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]


class DailyBonusResponse(BaseModel):
    ledger_id: int
    amount: int
    reason: str
    # 最初に渡す日（決めた日）
    starts_on: date
    # 渡し終えた最後の日。まだ 1 日も渡していなければ null
    granted_through: date | None


class LedgerResponse(BaseModel):
    ledger_id: int
    family_id: int
    membership_id: int
    display_name: str
    balance: int
    can_modify: bool
    transactions: list[TransactionResponse]
    # 毎日のボーナスの設定（ADR-0024）。決めていなければ null
    daily_bonus: DailyBonusResponse | None


__all__ = [
    "ChildCreateRequest",
    "CorrectionCreateRequest",
    "CorrectionResponse",
    "DailyBonusRequest",
    "DailyBonusResponse",
    "FamilyCreateRequest",
    "FamilyDetailResponse",
    "FamilyRenameRequest",
    "FamilySummaryResponse",
    "InvitationAcceptRequest",
    "InvitationCreateRequest",
    "InvitationRedeemRequest",
    "InvitationResponse",
    "LedgerResponse",
    "MemberOrderRequest",
    "MembershipResponse",
    "NonBlankStr",
    "RedeemedInvitationResponse",
    "ReversalCreateRequest",
    "TemporaryPasswordResponse",
    "TransactionCreateRequest",
    "TransactionResponse",
]
