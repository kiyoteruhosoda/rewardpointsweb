"""控えを取り込む前に、書ける形かを確かめる（ADR-0025）。

項目の有無・型・長さは Pydantic が先に見る。ここが見るのは **中身の辻褄** で、
「この API を順に叩けば同じ家族が作れるか」を問う。作れない控えは 1 行も書かずに
断る — 取り込みは 1 つのトランザクションなので、途中で気付いても巻き戻るだけだが、
半端に書いた家族が残らないことを呼び出し側が読み取れる場所に置いておく。

台帳の決まり（打ち消しは打ち消せない・同じ行は 1 度しか打ち消せない・訂正は
打ち消しにはできない。ADR-0010 / ADR-0022）は、記録の入口と同じものをここでも
守る。控えから来た行だけが例外、という抜け道を作らない。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ARCHIVE_FORMAT,
    ARCHIVE_VERSION,
    ArchivedMemberDTO,
    ArchivedTransactionDTO,
    FamilyArchiveDTO,
)
from bounded_contexts.reward_points.domain.exceptions import (
    InvalidFamilyArchiveError,
    UnsupportedArchiveVersionError,
)


def require_importable(archive: FamilyArchiveDTO) -> None:
    """取り込める控えでなければ例外を投げる。"""
    _require_readable_format(archive)
    member_refs = _unique_refs(member.ref for member in archive.members)
    _require_single_owner(archive.members)
    for member in archive.members:
        _require_ledger_matches_role(member)
        if member.ledger is not None:
            _require_writable_history(member.ledger.transactions, member_refs=member_refs)


def _require_readable_format(archive: FamilyArchiveDTO) -> None:
    if archive.format != ARCHIVE_FORMAT:
        raise InvalidFamilyArchiveError
    # 知らない版は読めるところだけ読む、ということをしない。落ちた項目に記録が
    # 入っていた場合、取り込めたように見えて中身が減る
    if archive.version != ARCHIVE_VERSION:
        raise UnsupportedArchiveVersionError


def _unique_refs(refs: Iterable[str]) -> frozenset[str]:
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            raise InvalidFamilyArchiveError
        seen.add(ref)
    return frozenset(seen)


def _require_single_owner(members: Sequence[ArchivedMemberDTO]) -> None:
    """owner はちょうど 1 人。

    取り込んだ人がその席に就く（``ImportFamilyUseCase``）。0 人なら誰も家族を
    管理できず、2 人以上なら取り込んだ人がどちらの名前を継ぐか決められない。
    """
    owners = [member for member in members if member.role.can_administer_family]
    if len(owners) != 1:
        raise InvalidFamilyArchiveError


def _require_ledger_matches_role(member: ArchivedMemberDTO) -> None:
    """台帳を持つのは子だけ、そして子は必ず持つ（ADR-0009）。"""
    if (member.ledger is not None) != member.role.has_own_ledger:
        raise InvalidFamilyArchiveError


def _require_writable_history(entries: Sequence[ArchivedTransactionDTO], *, member_refs: frozenset[str]) -> None:
    history = _WrittenHistory()
    for entry in entries:
        # 記録した人は同じ家族の参加者。控えの外の誰かは指せない
        if entry.granted_by is not None and entry.granted_by not in member_refs:
            raise InvalidFamilyArchiveError
        history.append(entry)


class _WrittenHistory:
    """並び順に沿って「ここまでに書いた行」を追う。

    控えは書いた順に並ぶので、打ち消し・訂正の相手は必ず**それより前**にある。
    前にしか繋がらないことを確かめれば、輪になった参照も、まだ無い行を指す参照も
    同じ 1 つの規則で落ちる。
    """

    def __init__(self) -> None:
        self._amounts: dict[str, int] = {}
        self._reversals: set[str] = set()
        self._reversed: set[str] = set()
        self._corrected: set[str] = set()

    def append(self, entry: ArchivedTransactionDTO) -> None:
        if entry.ref in self._amounts:
            raise InvalidFamilyArchiveError
        self._claim_reversal(entry)
        self._claim_correction(entry)
        self._amounts[entry.ref] = entry.amount
        if entry.reverses is not None:
            self._reversals.add(entry.ref)

    def _claim_reversal(self, entry: ArchivedTransactionDTO) -> None:
        target = entry.reverses
        if target is None:
            return
        # 打ち消しは打ち消せず（ADR-0010）、同じ行を 2 度は打ち消せない
        # （``UNIQUE (reversal_of_id)``）
        if target in self._reversals or target in self._reversed:
            raise InvalidFamilyArchiveError
        # 打ち消しは逆符号（``PointTransaction.plan_reversal``）。ここが崩れた控えは、
        # この API を通しては作れない残高を持つ
        if entry.amount != -self._amount_of(target):
            raise InvalidFamilyArchiveError
        self._reversed.add(target)

    def _claim_correction(self, entry: ArchivedTransactionDTO) -> None:
        target = entry.corrects
        if target is None:
            return
        # 打ち消しの行は訂正できず（ADR-0022）、同じ行の言い直しは 1 度だけ
        # （``UNIQUE (corrects_id)``）
        if target in self._reversals or target in self._corrected:
            raise InvalidFamilyArchiveError
        self._amount_of(target)
        self._corrected.add(target)

    def _amount_of(self, ref: str) -> int:
        """まだ書いていない行は指せない。"""
        amount = self._amounts.get(ref)
        if amount is None:
            raise InvalidFamilyArchiveError
        return amount


__all__ = ["require_importable"]
