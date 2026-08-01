"""reward_points コンテキストのドメイン例外。

Presentation 層が HTTP ステータス＋エラーコードへ変換する（表示文言への変換は
フロントエンド。CLAUDE.md「国際化」参照）。
"""

from __future__ import annotations


class RewardPointsError(Exception):
    """このコンテキストの基底例外。``code`` がそのまま API のエラーコードになる。"""

    code = "reward_points_error"


class FamilyNotFoundError(RewardPointsError):
    """家族そのものが存在しない。

    「所属していない」はこれではなく :class:`FamilyAccessDeniedError`。参加が
    引けない時点で止まるため、呼び出し元からは実在と未所属を区別できない。
    こちらは、参加は引けたのに家族の行が無いという壊れた状態のときだけ出る。
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


class RoleNotInvitableError(RewardPointsError):
    """招待では配れない立場（owner）を指定した。"""

    code = "role_not_invitable"


class InvitationTargetUnavailableError(RewardPointsError):
    """招待が指す参加者に、すでに別のアカウントが結び付いている。"""

    code = "invitation_target_unavailable"


class AccountAlreadyInFamilyError(RewardPointsError):
    """同一家族に、そのアカウントの参加者がすでに存在する。

    ``UNIQUE (family_id, account_id)``（ADR-0009）と同じ不変条件。
    """

    code = "account_already_in_family"


class AlreadyBelongsToFamilyError(RewardPointsError):
    """すでにどこかの家族に所属しているアカウントが、家族を作る・加わろうとした。

    所属できる家族は 1 アカウント 1 つまで（ADR-0013）。抜けて初期状態に
    戻ってから、作り直すか招待を受け直す。
    """

    code = "already_belongs_to_family"


class ChildCannotLeaveFamilyError(RewardPointsError):
    """``role = child``（ゲスト）が自分から家族を抜けようとした。

    子は自分では抜けられない（ADR-0013）。家族の構成を変えるのは owner の役目。
    """

    code = "child_cannot_leave_family"


class LastGuardianCannotLeaveError(RewardPointsError):
    """最後の親（owner / parent）が家族を抜けようとした。

    抜けられるのは他に親が残る場合だけ（ADR-0013）。親が誰もいなくなると、
    残された子の台帳を扱える人がいなくなる。1 人だけなら脱退ではなく解散を使う。
    """

    code = "last_guardian_cannot_leave"


class FamilyNotEmptyError(RewardPointsError):
    """自分以外の参加者が残っている家族を解散しようとした。

    参加者（親も子も）がいるうちは解散できない（ADR-0013）。台帳ごと黙って
    消える経路を作らない（ADR-0010）。
    """

    code = "family_not_empty"


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
    "AlreadyBelongsToFamilyError",
    "ChildAccountRequiredError",
    "ChildCannotLeaveFamilyError",
    "DisplayNameRequiredError",
    "FamilyAccessDeniedError",
    "FamilyNotEmptyError",
    "FamilyNotFoundError",
    "InvitationNotFoundError",
    "InvitationTargetUnavailableError",
    "LastGuardianCannotLeaveError",
    "LedgerNotEmptyError",
    "LedgerNotFoundError",
    "MembershipNotFoundError",
    "MembershipNotLinkedError",
    "ReversalOfReversalError",
    "RewardPointsError",
    "RoleNotInvitableError",
    "TransactionAlreadyReversedError",
    "TransactionNotFoundError",
    "UserStillOwnsFamiliesError",
    "UsernameAlreadyTakenError",
]
