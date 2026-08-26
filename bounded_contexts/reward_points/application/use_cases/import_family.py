"""控えから家族を作り直す（復元。ADR-0026）。

取り込みは必ず **新しい家族** を作る。既存の家族へ混ぜる道は用意しない — 同じ
名前の子が 2 人並んだとき、どちらが控えの子でどちらが今の子かを決められるのは
人だけで、機械が選ぶと台帳が静かに二重になる。

取り込んだ人が owner の席に就く。控えに載っていた owner の呼び名はそのまま
引き継ぐので、画面の並びは書き出したときと同じに戻る。**他の参加者はアカウント
未紐付けで作られる** — 控えにアカウントが入っていないため（ADR-0026）、本人が
入り直す道は招待コード（ADR-0011）になる。子は台帳ごと復元されるので、招待を
受けた子は自分の記録が残ったままログインできる。

台帳の行はすべて **追記** として書く（ADR-0010）。出来事の日時は控えのものを
使い、記録された日時は取り込んだ今になる — この行が今この DB へ書かれたことは
事実で、そこを偽らない。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application import family_archive_rules
from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    FamilyArchiveDTO,
    ImportedFamilyDTO,
)
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import AlreadyBelongsToFamilyError
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import (
    DailyBonusDraft,
    IDailyBonusRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from shared.kernel.timestamps import as_naive_utc

#: 取り込んだ行の冪等キーの頭。控えの ref がそのまま続く（``import-t1``）。
#:
#: 控えの ref は台帳の中で一意（``family_archive_rules``）なので、キーも
#: ``UNIQUE (ledger_id, idempotency_key)`` を満たす。書き出し元のキーは持ち込まない
#: — あれは「同じ要求が二度届いたか」を見るための鍵で、別の台帳へ運ぶ意味がない。
IMPORT_KEY_PREFIX = "import-"


@dataclass(frozen=True, kw_only=True)
class ImportFamilyCommand:
    account_id: int
    archive: FamilyArchiveDTO


class ImportFamilyUseCase:
    def __init__(
        self,
        *,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        bonuses: IDailyBonusRepository,
    ) -> None:
        self._families = families
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._bonuses = bonuses

    def execute(self, command: ImportFamilyCommand) -> ImportedFamilyDTO:
        archive = command.archive
        family_archive_rules.require_importable(archive)
        # 所属できる家族は 1 つまで（ADR-0013）。作成と同じ条件で断る
        if self._memberships.list_for_account(command.account_id):
            raise AlreadyBelongsToFamilyError

        family = self._families.add(name=archive.family_name, rules=archive.family_rules)
        members = self._restore_members(family_id=family.id, command=command)
        written = sum(self._restore_ledger(member, family_id=family.id, members=members) for member in archive.members)
        return ImportedFamilyDTO(
            family_id=family.id,
            name=family.name_value,
            member_count=len(members),
            transaction_count=written,
        )

    def _restore_members(self, *, family_id: int, command: ImportFamilyCommand) -> dict[str, FamilyMembership]:
        """控えの順に参加を作る（並び順は作った順に付く）。

        owner だけが取り込んだ人と結び付く。残りは未紐付けで、招待コードを
        受け取った本人が後から入る（ADR-0011）。
        """
        return {
            member.ref: self._memberships.add(
                family_id=family_id,
                account_id=command.account_id if member.role.can_administer_family else None,
                role=member.role,
                display_name=member.display_name,
            )
            for member in command.archive.members
        }

    def _restore_ledger(
        self, member: ArchivedMemberDTO, *, family_id: int, members: dict[str, FamilyMembership]
    ) -> int:
        """子の台帳を作り、記録と毎日のボーナスを戻す。書いた行数を返す。"""
        if member.ledger is None:
            return 0
        ledger = self._ledgers.add(family_id=family_id, membership_id=members[member.ref].id)
        written = self._append_history(member.ledger, ledger_id=ledger.id, members=members)
        self._restore_daily_bonus(member.ledger, ledger_id=ledger.id)
        return written

    def _append_history(
        self, archived: ArchivedLedgerDTO, *, ledger_id: int, members: dict[str, FamilyMembership]
    ) -> int:
        # 控えは書いた順に並ぶので、打ち消し・訂正が指す相手はここまでに書き終えている
        ids: dict[str, int] = {}
        for entry in archived.transactions:
            actor = members[entry.granted_by] if entry.granted_by else None
            appended = self._transactions.append(
                NewTransaction(
                    ledger_id=ledger_id,
                    amount=entry.amount,
                    reason=entry.reason,
                    granted_by_membership_id=actor.id if actor else None,
                    # 控えは外から来る JSON。オフセット付き（書き出しは ``Z``）で
                    # 載っているので、保存値と同じ UTC naive へ揃えてから書く
                    occurred_at=as_naive_utc(entry.occurred_at),
                    idempotency_key=f"{IMPORT_KEY_PREFIX}{entry.ref}",
                    reversal_of_id=ids[entry.reverses] if entry.reverses else None,
                    corrects_id=ids[entry.corrects] if entry.corrects else None,
                )
            )
            ids[entry.ref] = appended.id
        return len(archived.transactions)

    def _restore_daily_bonus(self, archived: ArchivedLedgerDTO, *, ledger_id: int) -> None:
        bonus = archived.daily_bonus
        if bonus is None:
            return
        saved = self._bonuses.save(
            DailyBonusDraft(
                ledger_id=ledger_id,
                amount=bonus.amount,
                reason=bonus.reason,
                starts_on=bonus.starts_on,
            )
        )
        # 渡し終えた日まで戻す。落とすと、控えに入っている日のボーナスが
        # 取り込んだ直後にもう一度足される（ADR-0024 の追いつき）
        if bonus.granted_through is not None:
            self._bonuses.mark_granted_through(bonus_id=saved.id, day=bonus.granted_through)


__all__ = ["IMPORT_KEY_PREFIX", "ImportFamilyCommand", "ImportFamilyUseCase"]
