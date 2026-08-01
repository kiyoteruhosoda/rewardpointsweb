"""reward_points コンテキストのドメイン例外。

Presentation 層が HTTP ステータス＋エラーコードへ変換する（表示文言への変換は
フロントエンド。CLAUDE.md「国際化」参照）。
"""

from __future__ import annotations


class RewardPointsError(Exception):
    """このコンテキストの基底例外。``code`` がそのまま API のエラーコードになる。"""

    code = "reward_points_error"


class FamilyNotFoundError(RewardPointsError):
    """家族が存在しない、または呼び出し元が所属していない。

    所属していない家族は「無い」ものとして扱う。403 を返すと、その ID の家族が
    存在することが分かってしまう（ADR-0009 のデータ分離境界）。
    """

    code = "family_not_found"


class FamilyAccessDeniedError(RewardPointsError):
    """家族には所属しているが、その操作を行える立場ではない。"""

    code = "family_access_denied"


class MembershipNotFoundError(RewardPointsError):
    """参加者が存在しない（他の家族の参加者を指した場合も含む）。"""

    code = "membership_not_found"


class LedgerNotFoundError(RewardPointsError):
    """台帳が存在しない、または閲覧できる立場ではない。"""

    code = "ledger_not_found"


class TransactionNotFoundError(RewardPointsError):
    """トランザクションが存在しない（他の台帳のものを指した場合も含む）。"""

    code = "transaction_not_found"


class TransactionAlreadyReversedError(RewardPointsError):
    """すでに打ち消し済みのトランザクションを、もう一度打ち消そうとした。"""

    code = "transaction_already_reversed"


class ReversalOfReversalError(RewardPointsError):
    """打ち消しレコード自体を打ち消そうとした（ADR-0010 で禁じている）。"""

    code = "reversal_of_reversal_not_allowed"


class InvitationNotFoundError(RewardPointsError):
    """招待コードが存在しない、期限切れ、または使用済み。

    3 つを区別しない。区別すると、有効なコードを総当たりで探す手がかりになる。
    """

    code = "invitation_not_found"


class InvitationTargetUnavailableError(RewardPointsError):
    """招待が指す参加者に、すでに別のアカウントが結び付いている。"""

    code = "invitation_target_unavailable"


class AccountAlreadyInFamilyError(RewardPointsError):
    """同一家族に、そのアカウントの参加者がすでに存在する。

    ``UNIQUE (family_id, account_id)``（ADR-0009）と同じ不変条件。
    """

    code = "account_already_in_family"


class UsernameAlreadyTakenError(RewardPointsError):
    """指定されたログイン ID はすでに使われている。"""

    code = "username_already_taken"


class ChildAccountRequiredError(RewardPointsError):
    """親から親へのパスワードリセットを試みた。

    一時パスワードの発行は ``role = child`` の参加者に対してだけ許す（ADR-0011）。
    """

    code = "child_account_required"


class DisplayNameRequiredError(RewardPointsError):
    """呼び名の要る招待（参加者を指していない招待）に、呼び名が渡されなかった。"""

    code = "display_name_required"


class MembershipNotLinkedError(RewardPointsError):
    """アカウントがまだ結び付いていない参加者に、アカウント側の操作を求めた。"""

    code = "membership_not_linked"


class LedgerNotEmptyError(RewardPointsError):
    """記録の残っている台帳ごと参加者を削除しようとした。

    台帳は追記専用で、消す手段を用意していない（ADR-0010）。参加者を外したい
    場合も、記録が残っているうちは断る。
    """

    code = "ledger_not_empty"


class UserStillOwnsFamiliesError(RewardPointsError):
    """家族の owner として残っているアカウントは削除できない。

    owner が消えるとその家族を管理できる人がいなくなる。黙って一緒に消すと
    台帳まで失われるため、先に家族を片付けてもらう。
    """

    code = "user_still_owns_families"


__all__ = [
    "AccountAlreadyInFamilyError",
    "ChildAccountRequiredError",
    "DisplayNameRequiredError",
    "FamilyAccessDeniedError",
    "FamilyNotFoundError",
    "InvitationNotFoundError",
    "InvitationTargetUnavailableError",
    "LedgerNotEmptyError",
    "LedgerNotFoundError",
    "MembershipNotFoundError",
    "MembershipNotLinkedError",
    "ReversalOfReversalError",
    "RewardPointsError",
    "TransactionAlreadyReversedError",
    "TransactionNotFoundError",
    "UserStillOwnsFamiliesError",
    "UsernameAlreadyTakenError",
]
