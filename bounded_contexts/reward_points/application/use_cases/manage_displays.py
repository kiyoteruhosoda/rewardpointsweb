"""表示端末を家族へ付ける・外す・一覧する（運用管理者。ADR-0047）。

ここに来る呼び出しは ``display:approve`` を持つ人（運用管理者）か、端末そのものの
取り直し（``/api/display/session``）に限る。運用管理者は家族の参加者ではないので、
:class:`FamilyAccessResolver` は通さない ——どの家族を映すかを決めるのがこの役の仕事で、
認可は scope（router）で済んでいる。

家族の側から外す経路（親が家族の画面で外す）は :class:`RemoveMembershipUseCase` が持つ。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.display_dto import DisplayableFamilyDTO, DisplayDTO
from bounded_contexts.reward_points.domain.entities.family import Family
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import DisplayNotFoundError, FamilyNotFoundError
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class AttachDisplayCommand:
    family_id: int
    #: 端末の名前（例「リビング」）
    name: str


class DisplayRoster:
    """表示端末の名簿。付ける・外す・引く・並べるをまとめて持つ。"""

    def __init__(
        self,
        *,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
        provisioning: IAccountProvisioning,
    ) -> None:
        self._families = families
        self._memberships = memberships
        self._provisioning = provisioning

    def attach(self, command: AttachDisplayCommand) -> DisplayDTO:
        """表示アカウントを作り、家族へ表示端末として加える。"""
        family = self._families.find_by_id(command.family_id)
        if family is None:
            raise FamilyNotFoundError
        name = DisplayName(command.name.strip()).value
        account = self._provisioning.create_display_account(display_name=name)
        membership = self._memberships.add(
            family_id=family.id,
            account_id=account.account_id,
            role=FamilyRole.DISPLAY,
            display_name=name,
        )
        return _to_dto(membership, family)

    def detach(self, account_id: int) -> DisplayDTO:
        """表示端末を外す。参加とアカウントの両方を消す（1 端末 = 1 アカウント）。"""
        found = self.find(account_id)
        if found is None:
            raise DisplayNotFoundError
        self._memberships.delete(found.membership_id)
        self._provisioning.delete_account(account_id)
        return found

    def find(self, account_id: int) -> DisplayDTO | None:
        """*account_id* が表示端末として家族に付いていれば、その端末。"""
        membership = next((m for m in self._memberships.list_for_account(account_id) if m.role.is_display), None)
        if membership is None:
            return None
        family = self._families.find_by_id(membership.family_id)
        return None if family is None else _to_dto(membership, family)

    def list_all(self) -> list[DisplayDTO]:
        displays = self._memberships.list_displays()
        families = {family.id: family for family in self._families.list_by_ids([d.family_id for d in displays])}
        return [_to_dto(display, families[display.family_id]) for display in displays if display.family_id in families]

    def families_to_display(self) -> list[DisplayableFamilyDTO]:
        return [DisplayableFamilyDTO(id=family.id, name=family.name_value) for family in self._families.list_all()]


def _to_dto(membership: FamilyMembership, family: Family) -> DisplayDTO:
    if membership.account_id is None:  # 表示端末は承認の時点でアカウントと結び付いている
        raise DisplayNotFoundError
    return DisplayDTO(
        account_id=membership.account_id,
        membership_id=membership.id,
        family_id=family.id,
        family_name=family.name_value,
        name=membership.display_name_value,
        created_at=membership.created_at,
    )


__all__ = ["AttachDisplayCommand", "DisplayRoster"]
