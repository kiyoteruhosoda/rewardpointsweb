"""reward_points コンテキストの Pydantic スキーマ。

長さ・上限はドメインの値オブジェクトの定数を使う（同じ数字を書き写さない）。
``access_level`` / ``entry_type`` はドメインの列挙をそのまま使い、JSON へは値
（``"view"`` / ``"addition"`` 等）が出る。OpenAPI にも列挙として現れる。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from bounded_contexts.reward_points.domain.value_objects.entry_description import (
    MAX_LENGTH as DESCRIPTION_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel
from bounded_contexts.reward_points.domain.value_objects.member_name import MAX_LENGTH as NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_VALUE as POINTS_MAX
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType


def _non_blank(value: str) -> str:
    """前後の空白を落とし、空白だけの入力を弾く。

    ``min_length=1`` は空白 1 文字を通してしまうため、表示される値は落としてから
    長さを見る。
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]


class MemberCreateRequest(BaseModel):
    name: Annotated[NonBlankStr, Field(max_length=NAME_MAX_LENGTH)]
    # 指定するとメンバー本人が自分のポイントを閲覧できる（変更はできない）
    linked_user_email: EmailStr | None = None


class MemberSummaryResponse(BaseModel):
    id: int
    name: str
    balance: int
    access_level: MemberAccessLevel
    is_self: bool
    has_linked_user: bool


class MemberResponse(BaseModel):
    id: int
    name: str
    balance: int
    access_level: MemberAccessLevel
    is_self: bool
    linked_user_email: str | None


class PointAdditionRequest(BaseModel):
    points: int = Field(gt=0, le=POINTS_MAX)
    reason: Annotated[NonBlankStr, Field(max_length=DESCRIPTION_MAX_LENGTH)]
    # 未指定なら受け付けた時刻（UTC）
    occurred_at: datetime | None = None


class PointConsumptionRequest(BaseModel):
    points: int = Field(gt=0, le=POINTS_MAX)
    application: Annotated[NonBlankStr, Field(max_length=DESCRIPTION_MAX_LENGTH)]
    occurred_at: datetime | None = None


class PointEntryResponse(BaseModel):
    id: int
    entry_type: PointEntryType
    occurred_at: datetime
    points: int
    signed_points: int
    description: str


class PointLedgerResponse(BaseModel):
    member_id: int
    member_name: str
    balance: int
    access_level: MemberAccessLevel
    entries: list[PointEntryResponse]


class MemberShareRequest(BaseModel):
    email: EmailStr
    access_level: MemberAccessLevel = MemberAccessLevel.VIEW


class MemberShareResponse(BaseModel):
    user_id: int
    email: str
    username: str
    access_level: MemberAccessLevel


__all__ = [
    "MemberCreateRequest",
    "MemberResponse",
    "MemberShareRequest",
    "MemberShareResponse",
    "MemberSummaryResponse",
    "NonBlankStr",
    "PointAdditionRequest",
    "PointConsumptionRequest",
    "PointEntryResponse",
    "PointLedgerResponse",
]
