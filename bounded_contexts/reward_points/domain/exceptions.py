"""reward_points コンテキストのドメイン例外。

Presentation 層が HTTP ステータス＋エラーコードへ変換する（表示文言への変換は
フロントエンド。CLAUDE.md「国際化」参照）。
"""

from __future__ import annotations


class RewardPointsError(Exception):
    """このコンテキストの基底例外。``code`` がそのまま API のエラーコードになる。"""

    code = "reward_points_error"


class MemberNotFoundError(RewardPointsError):
    """メンバーが存在しない。"""

    code = "member_not_found"


class MemberAccessDeniedError(RewardPointsError):
    """そのメンバーへ、要求された操作をする権限が無い。

    「存在しない」と区別せずに済む場面ではこちらを返さない（他人のメンバーの
    存在を推測させないため、参照権すら無い相手には
    :class:`MemberNotFoundError` を返す）。
    """

    code = "member_access_denied"


class PointEntryNotFoundError(RewardPointsError):
    """履歴が存在しない（他のメンバーの履歴を指した場合も含む）。"""

    code = "point_entry_not_found"


class ShareTargetNotFoundError(RewardPointsError):
    """共有先として指定されたユーザーが見つからない。"""

    code = "share_target_not_found"


class MemberShareNotFoundError(RewardPointsError):
    """取り消そうとした共有が存在しない。"""

    code = "member_share_not_found"


class MemberAlreadySharedError(RewardPointsError):
    """すでに共有済みの相手を、もう一度共有しようとした。"""

    code = "member_already_shared"


class ShareWithOwnerNotAllowedError(RewardPointsError):
    """所有者自身を共有先に指定した（所有者はもともと変更できる）。"""

    code = "share_with_owner_not_allowed"


class LinkedUserAlreadyTakenError(RewardPointsError):
    """そのログインアカウントは、すでに別のメンバーへ紐付いている。"""

    code = "linked_user_already_taken"


__all__ = [
    "LinkedUserAlreadyTakenError",
    "MemberAccessDeniedError",
    "MemberAlreadySharedError",
    "MemberNotFoundError",
    "MemberShareNotFoundError",
    "PointEntryNotFoundError",
    "RewardPointsError",
    "ShareTargetNotFoundError",
    "ShareWithOwnerNotAllowedError",
]
