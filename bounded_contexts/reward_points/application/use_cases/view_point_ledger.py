"""ポイント台帳（残高と履歴）を見る。

閲覧だけなら ``VIEW`` で足りる。応答に ``access_level`` を含めるので、画面側は
「変更 UI を出すか」をこの 1 つの値で決められる（役割名で分岐しない）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.point_entry_dto import PointEntryDTO, PointLedgerDTO
from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository
from bounded_contexts.reward_points.domain.services.point_ledger import PointLedger


class ViewPointLedgerUseCase:
    def __init__(self, access: MemberAccessResolver, entries: IPointEntryRepository) -> None:
        self._access = access
        self._entries = entries

    def execute(self, *, member_id: int, user_id: int) -> PointLedgerDTO:
        access = self._access.resolve(member_id=member_id, user_id=user_id)
        ledger = PointLedger(self._entries.list_by_member(member_id))
        return PointLedgerDTO(
            member_id=access.member.id,
            member_name=access.member.name_value,
            balance=ledger.balance.value,
            access_level=access.level,
            is_owner=access.member.is_owned_by(user_id),
            entries=tuple(PointEntryDTO.of(entry) for entry in ledger.entries),
        )


__all__ = ["ViewPointLedgerUseCase"]
