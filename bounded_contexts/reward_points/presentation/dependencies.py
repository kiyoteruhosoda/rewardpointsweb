"""``Depends()`` 用の組み立て。

具象リポジトリを作ってユースケースへ注入するのはこの層の仕事（最も外側で配線する）。
ルーター本体は「ユースケースを 1 回呼ぶ」だけに保つ。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.application.use_cases.delete_member import DeleteMemberUseCase
from bounded_contexts.reward_points.application.use_cases.delete_point_entry import DeletePointEntryUseCase
from bounded_contexts.reward_points.application.use_cases.list_accessible_members import (
    ListAccessibleMembersUseCase,
)
from bounded_contexts.reward_points.application.use_cases.list_member_shares import ListMemberSharesUseCase
from bounded_contexts.reward_points.application.use_cases.record_point_addition import (
    RecordPointAdditionUseCase,
)
from bounded_contexts.reward_points.application.use_cases.record_point_consumption import (
    RecordPointConsumptionUseCase,
)
from bounded_contexts.reward_points.application.use_cases.register_member import RegisterMemberUseCase
from bounded_contexts.reward_points.application.use_cases.revoke_member_share import RevokeMemberShareUseCase
from bounded_contexts.reward_points.application.use_cases.share_member import ShareMemberUseCase
from bounded_contexts.reward_points.application.use_cases.view_point_ledger import ViewPointLedgerUseCase
from bounded_contexts.reward_points.infrastructure.sql_member_repository import SqlMemberRepository
from bounded_contexts.reward_points.infrastructure.sql_member_share_repository import (
    SqlMemberShareRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_entry_repository import (
    SqlPointEntryRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_share_target_directory import (
    SqlShareTargetDirectory,
)
from shared.kernel.database.session import get_db

DbDep = Annotated[Session, Depends(get_db)]


# --- リポジトリ --------------------------------------------------------------


def get_member_repository(db: DbDep) -> SqlMemberRepository:
    return SqlMemberRepository(db)


def get_member_share_repository(db: DbDep) -> SqlMemberShareRepository:
    return SqlMemberShareRepository(db)


def get_point_entry_repository(db: DbDep) -> SqlPointEntryRepository:
    return SqlPointEntryRepository(db)


def get_share_target_directory(db: DbDep) -> SqlShareTargetDirectory:
    return SqlShareTargetDirectory(db)


MemberRepoDep = Annotated[SqlMemberRepository, Depends(get_member_repository)]
ShareRepoDep = Annotated[SqlMemberShareRepository, Depends(get_member_share_repository)]
EntryRepoDep = Annotated[SqlPointEntryRepository, Depends(get_point_entry_repository)]
DirectoryDep = Annotated[SqlShareTargetDirectory, Depends(get_share_target_directory)]


def get_member_access_resolver(members: MemberRepoDep, shares: ShareRepoDep) -> MemberAccessResolver:
    return MemberAccessResolver(members, shares)


AccessDep = Annotated[MemberAccessResolver, Depends(get_member_access_resolver)]


# --- ユースケース ------------------------------------------------------------


def get_list_members_use_case(
    members: MemberRepoDep, shares: ShareRepoDep, entries: EntryRepoDep
) -> ListAccessibleMembersUseCase:
    return ListAccessibleMembersUseCase(members, shares, entries)


def get_register_member_use_case(members: MemberRepoDep, directory: DirectoryDep) -> RegisterMemberUseCase:
    return RegisterMemberUseCase(members, directory)


def get_delete_member_use_case(access: AccessDep, members: MemberRepoDep) -> DeleteMemberUseCase:
    return DeleteMemberUseCase(access, members)


def get_view_ledger_use_case(access: AccessDep, entries: EntryRepoDep) -> ViewPointLedgerUseCase:
    return ViewPointLedgerUseCase(access, entries)


def get_record_addition_use_case(access: AccessDep, entries: EntryRepoDep) -> RecordPointAdditionUseCase:
    return RecordPointAdditionUseCase(access, entries)


def get_record_consumption_use_case(access: AccessDep, entries: EntryRepoDep) -> RecordPointConsumptionUseCase:
    return RecordPointConsumptionUseCase(access, entries)


def get_delete_entry_use_case(access: AccessDep, entries: EntryRepoDep) -> DeletePointEntryUseCase:
    return DeletePointEntryUseCase(access, entries)


def get_list_shares_use_case(
    access: AccessDep, shares: ShareRepoDep, directory: DirectoryDep
) -> ListMemberSharesUseCase:
    return ListMemberSharesUseCase(access, shares, directory)


def get_share_member_use_case(access: AccessDep, shares: ShareRepoDep, directory: DirectoryDep) -> ShareMemberUseCase:
    return ShareMemberUseCase(access, shares, directory)


def get_revoke_share_use_case(access: AccessDep, shares: ShareRepoDep) -> RevokeMemberShareUseCase:
    return RevokeMemberShareUseCase(access, shares)


ListMembersDep = Annotated[ListAccessibleMembersUseCase, Depends(get_list_members_use_case)]
RegisterMemberDep = Annotated[RegisterMemberUseCase, Depends(get_register_member_use_case)]
DeleteMemberDep = Annotated[DeleteMemberUseCase, Depends(get_delete_member_use_case)]
ViewLedgerDep = Annotated[ViewPointLedgerUseCase, Depends(get_view_ledger_use_case)]
RecordAdditionDep = Annotated[RecordPointAdditionUseCase, Depends(get_record_addition_use_case)]
RecordConsumptionDep = Annotated[RecordPointConsumptionUseCase, Depends(get_record_consumption_use_case)]
DeleteEntryDep = Annotated[DeletePointEntryUseCase, Depends(get_delete_entry_use_case)]
ListSharesDep = Annotated[ListMemberSharesUseCase, Depends(get_list_shares_use_case)]
ShareMemberDep = Annotated[ShareMemberUseCase, Depends(get_share_member_use_case)]
RevokeShareDep = Annotated[RevokeMemberShareUseCase, Depends(get_revoke_share_use_case)]


__all__ = [
    "AccessDep",
    "DeleteEntryDep",
    "DeleteMemberDep",
    "ListMembersDep",
    "ListSharesDep",
    "RecordAdditionDep",
    "RecordConsumptionDep",
    "RegisterMemberDep",
    "RevokeShareDep",
    "ShareMemberDep",
    "ViewLedgerDep",
]
