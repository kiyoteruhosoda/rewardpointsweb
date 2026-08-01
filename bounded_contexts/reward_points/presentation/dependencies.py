"""``Depends()`` 用の組み立て。

具象リポジトリを作ってユースケースへ注入するのはこの層の仕事（最も外側で配線する）。
ルーター本体は「ユースケースを 1 回呼ぶ」だけに保つ。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_overview_builder import FamilyOverviewBuilder
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.application.use_cases.accept_invitation import AcceptInvitationUseCase
from bounded_contexts.reward_points.application.use_cases.add_child_membership import (
    AddChildMembershipUseCase,
)
from bounded_contexts.reward_points.application.use_cases.approve_independence import (
    ApproveIndependenceUseCase,
)
from bounded_contexts.reward_points.application.use_cases.create_family import CreateFamilyUseCase
from bounded_contexts.reward_points.application.use_cases.dissolve_family import DissolveFamilyUseCase
from bounded_contexts.reward_points.application.use_cases.ensure_user_can_be_deleted import (
    EnsureUserCanBeDeletedUseCase,
)
from bounded_contexts.reward_points.application.use_cases.issue_invitation import IssueInvitationUseCase
from bounded_contexts.reward_points.application.use_cases.leave_family import LeaveFamilyUseCase
from bounded_contexts.reward_points.application.use_cases.list_families import ListFamiliesUseCase
from bounded_contexts.reward_points.application.use_cases.list_invitations import ListInvitationsUseCase
from bounded_contexts.reward_points.application.use_cases.propose_independence import (
    ProposeIndependenceUseCase,
    RevokeIndependenceProposalUseCase,
)
from bounded_contexts.reward_points.application.use_cases.record_point_transaction import (
    RecordPointTransactionUseCase,
)
from bounded_contexts.reward_points.application.use_cases.redeem_invitation import RedeemInvitationUseCase
from bounded_contexts.reward_points.application.use_cases.remove_membership import RemoveMembershipUseCase
from bounded_contexts.reward_points.application.use_cases.rename_family import RenameFamilyUseCase
from bounded_contexts.reward_points.application.use_cases.reset_child_password import (
    ResetChildPasswordUseCase,
)
from bounded_contexts.reward_points.application.use_cases.reverse_point_transaction import (
    ReversePointTransactionUseCase,
)
from bounded_contexts.reward_points.application.use_cases.revoke_invitation import RevokeInvitationUseCase
from bounded_contexts.reward_points.application.use_cases.suggest_transaction_reasons import (
    SuggestTransactionReasonsUseCase,
)
from bounded_contexts.reward_points.application.use_cases.view_family import ViewFamilyUseCase
from bounded_contexts.reward_points.application.use_cases.view_point_ledger import ViewPointLedgerUseCase
from bounded_contexts.reward_points.infrastructure.sql_account_directory import (
    SqlAccountDirectory,
    SqlAccountProvisioning,
)
from bounded_contexts.reward_points.infrastructure.sql_family_invitation_repository import (
    SqlFamilyInvitationRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_family_membership_repository import (
    SqlFamilyMembershipRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_family_repository import SqlFamilyRepository
from bounded_contexts.reward_points.infrastructure.sql_point_ledger_repository import (
    SqlPointLedgerRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_transaction_repository import (
    SqlPointTransactionRepository,
)
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

DbDep = Annotated[Session, Depends(get_db)]


# --- リポジトリ --------------------------------------------------------------


def get_family_repository(db: DbDep) -> SqlFamilyRepository:
    return SqlFamilyRepository(db)


def get_membership_repository(db: DbDep) -> SqlFamilyMembershipRepository:
    return SqlFamilyMembershipRepository(db)


def get_ledger_repository(db: DbDep) -> SqlPointLedgerRepository:
    return SqlPointLedgerRepository(db)


def get_transaction_repository(db: DbDep) -> SqlPointTransactionRepository:
    return SqlPointTransactionRepository(db)


def get_invitation_repository(db: DbDep) -> SqlFamilyInvitationRepository:
    return SqlFamilyInvitationRepository(db)


def get_account_directory(db: DbDep) -> SqlAccountDirectory:
    return SqlAccountDirectory(db)


def get_account_provisioning(db: DbDep) -> SqlAccountProvisioning:
    return SqlAccountProvisioning(db)


FamilyRepoDep = Annotated[SqlFamilyRepository, Depends(get_family_repository)]
MembershipRepoDep = Annotated[SqlFamilyMembershipRepository, Depends(get_membership_repository)]
LedgerRepoDep = Annotated[SqlPointLedgerRepository, Depends(get_ledger_repository)]
TransactionRepoDep = Annotated[SqlPointTransactionRepository, Depends(get_transaction_repository)]
InvitationRepoDep = Annotated[SqlFamilyInvitationRepository, Depends(get_invitation_repository)]
DirectoryDep = Annotated[SqlAccountDirectory, Depends(get_account_directory)]
ProvisioningDep = Annotated[SqlAccountProvisioning, Depends(get_account_provisioning)]


# --- 組み立て済みの協調オブジェクト ------------------------------------------


def get_access_resolver(memberships: MembershipRepoDep, ledgers: LedgerRepoDep) -> FamilyAccessResolver:
    return FamilyAccessResolver(memberships, ledgers)


AccessDep = Annotated[FamilyAccessResolver, Depends(get_access_resolver)]


def get_overview_builder(
    memberships: MembershipRepoDep,
    ledgers: LedgerRepoDep,
    transactions: TransactionRepoDep,
    directory: DirectoryDep,
) -> FamilyOverviewBuilder:
    return FamilyOverviewBuilder(memberships, ledgers, transactions, directory)


OverviewDep = Annotated[FamilyOverviewBuilder, Depends(get_overview_builder)]


def get_invitation_binder(
    invitations: InvitationRepoDep,
    memberships: MembershipRepoDep,
    ledgers: LedgerRepoDep,
) -> InvitationBinder:
    return InvitationBinder(invitations, memberships, ledgers)


BinderDep = Annotated[InvitationBinder, Depends(get_invitation_binder)]


# --- ユースケース ------------------------------------------------------------


def get_list_families_use_case(families: FamilyRepoDep, memberships: MembershipRepoDep) -> ListFamiliesUseCase:
    return ListFamiliesUseCase(families, memberships)


def get_create_family_use_case(families: FamilyRepoDep, memberships: MembershipRepoDep) -> CreateFamilyUseCase:
    return CreateFamilyUseCase(families, memberships)


def get_view_family_use_case(access: AccessDep, families: FamilyRepoDep, overview: OverviewDep) -> ViewFamilyUseCase:
    return ViewFamilyUseCase(access, families, overview)


def get_rename_family_use_case(
    access: AccessDep, families: FamilyRepoDep, overview: OverviewDep
) -> RenameFamilyUseCase:
    return RenameFamilyUseCase(access, families, overview)


def get_leave_family_use_case(access: AccessDep, memberships: MembershipRepoDep) -> LeaveFamilyUseCase:
    return LeaveFamilyUseCase(access, memberships)


def get_dissolve_family_use_case(
    access: AccessDep, families: FamilyRepoDep, memberships: MembershipRepoDep
) -> DissolveFamilyUseCase:
    return DissolveFamilyUseCase(access, families, memberships)


def get_propose_independence_use_case(access: AccessDep, memberships: MembershipRepoDep) -> ProposeIndependenceUseCase:
    return ProposeIndependenceUseCase(access, memberships)


def get_revoke_independence_use_case(
    access: AccessDep, memberships: MembershipRepoDep
) -> RevokeIndependenceProposalUseCase:
    return RevokeIndependenceProposalUseCase(access, memberships)


def get_approve_independence_use_case(
    access: AccessDep,
    memberships: MembershipRepoDep,
    ledgers: LedgerRepoDep,
    transactions: TransactionRepoDep,
    provisioning: ProvisioningDep,
) -> ApproveIndependenceUseCase:
    return ApproveIndependenceUseCase(access, memberships, ledgers, transactions, provisioning)


def get_add_child_use_case(
    access: AccessDep, memberships: MembershipRepoDep, ledgers: LedgerRepoDep
) -> AddChildMembershipUseCase:
    return AddChildMembershipUseCase(access, memberships, ledgers)


def get_remove_membership_use_case(
    access: AccessDep,
    memberships: MembershipRepoDep,
    ledgers: LedgerRepoDep,
    transactions: TransactionRepoDep,
) -> RemoveMembershipUseCase:
    return RemoveMembershipUseCase(access, memberships, ledgers, transactions)


def get_issue_invitation_use_case(
    access: AccessDep, invitations: InvitationRepoDep, memberships: MembershipRepoDep
) -> IssueInvitationUseCase:
    return IssueInvitationUseCase(
        access,
        invitations,
        memberships,
        timedelta(seconds=settings.family_invitation_ttl_seconds),
    )


def get_list_invitations_use_case(
    access: AccessDep, invitations: InvitationRepoDep, memberships: MembershipRepoDep
) -> ListInvitationsUseCase:
    return ListInvitationsUseCase(access, invitations, memberships)


def get_revoke_invitation_use_case(access: AccessDep, invitations: InvitationRepoDep) -> RevokeInvitationUseCase:
    return RevokeInvitationUseCase(access, invitations)


def get_accept_invitation_use_case(binder: BinderDep, families: FamilyRepoDep) -> AcceptInvitationUseCase:
    return AcceptInvitationUseCase(binder, families)


def get_redeem_invitation_use_case(
    binder: BinderDep,
    invitations: InvitationRepoDep,
    families: FamilyRepoDep,
    provisioning: ProvisioningDep,
) -> RedeemInvitationUseCase:
    return RedeemInvitationUseCase(binder, invitations, families, provisioning)


def get_reset_child_password_use_case(
    access: AccessDep,
    memberships: MembershipRepoDep,
    provisioning: ProvisioningDep,
    directory: DirectoryDep,
) -> ResetChildPasswordUseCase:
    return ResetChildPasswordUseCase(access, memberships, provisioning, directory)


def get_view_ledger_use_case(
    access: AccessDep, transactions: TransactionRepoDep, memberships: MembershipRepoDep
) -> ViewPointLedgerUseCase:
    return ViewPointLedgerUseCase(access, transactions, memberships)


def get_record_transaction_use_case(
    access: AccessDep, transactions: TransactionRepoDep
) -> RecordPointTransactionUseCase:
    return RecordPointTransactionUseCase(access, transactions)


def get_reverse_transaction_use_case(
    access: AccessDep, transactions: TransactionRepoDep
) -> ReversePointTransactionUseCase:
    return ReversePointTransactionUseCase(access, transactions)


def get_suggest_reasons_use_case(
    access: AccessDep, transactions: TransactionRepoDep
) -> SuggestTransactionReasonsUseCase:
    return SuggestTransactionReasonsUseCase(access, transactions)


def get_ensure_user_can_be_deleted_use_case(families: FamilyRepoDep) -> EnsureUserCanBeDeletedUseCase:
    return EnsureUserCanBeDeletedUseCase(families)


ListFamiliesDep = Annotated[ListFamiliesUseCase, Depends(get_list_families_use_case)]
CreateFamilyDep = Annotated[CreateFamilyUseCase, Depends(get_create_family_use_case)]
ViewFamilyDep = Annotated[ViewFamilyUseCase, Depends(get_view_family_use_case)]
RenameFamilyDep = Annotated[RenameFamilyUseCase, Depends(get_rename_family_use_case)]
LeaveFamilyDep = Annotated[LeaveFamilyUseCase, Depends(get_leave_family_use_case)]
DissolveFamilyDep = Annotated[DissolveFamilyUseCase, Depends(get_dissolve_family_use_case)]
ProposeIndependenceDep = Annotated[ProposeIndependenceUseCase, Depends(get_propose_independence_use_case)]
RevokeIndependenceDep = Annotated[RevokeIndependenceProposalUseCase, Depends(get_revoke_independence_use_case)]
ApproveIndependenceDep = Annotated[ApproveIndependenceUseCase, Depends(get_approve_independence_use_case)]
AddChildDep = Annotated[AddChildMembershipUseCase, Depends(get_add_child_use_case)]
RemoveMembershipDep = Annotated[RemoveMembershipUseCase, Depends(get_remove_membership_use_case)]
IssueInvitationDep = Annotated[IssueInvitationUseCase, Depends(get_issue_invitation_use_case)]
ListInvitationsDep = Annotated[ListInvitationsUseCase, Depends(get_list_invitations_use_case)]
RevokeInvitationDep = Annotated[RevokeInvitationUseCase, Depends(get_revoke_invitation_use_case)]
AcceptInvitationDep = Annotated[AcceptInvitationUseCase, Depends(get_accept_invitation_use_case)]
RedeemInvitationDep = Annotated[RedeemInvitationUseCase, Depends(get_redeem_invitation_use_case)]
ResetChildPasswordDep = Annotated[ResetChildPasswordUseCase, Depends(get_reset_child_password_use_case)]
ViewLedgerDep = Annotated[ViewPointLedgerUseCase, Depends(get_view_ledger_use_case)]
RecordTransactionDep = Annotated[RecordPointTransactionUseCase, Depends(get_record_transaction_use_case)]
ReverseTransactionDep = Annotated[ReversePointTransactionUseCase, Depends(get_reverse_transaction_use_case)]
SuggestReasonsDep = Annotated[SuggestTransactionReasonsUseCase, Depends(get_suggest_reasons_use_case)]


__all__ = [
    "AcceptInvitationDep",
    "AccessDep",
    "AddChildDep",
    "ApproveIndependenceDep",
    "CreateFamilyDep",
    "DissolveFamilyDep",
    "IssueInvitationDep",
    "LeaveFamilyDep",
    "ListFamiliesDep",
    "ListInvitationsDep",
    "ProposeIndependenceDep",
    "RecordTransactionDep",
    "RedeemInvitationDep",
    "RemoveMembershipDep",
    "RenameFamilyDep",
    "ResetChildPasswordDep",
    "ReverseTransactionDep",
    "RevokeIndependenceDep",
    "RevokeInvitationDep",
    "SuggestReasonsDep",
    "ViewFamilyDep",
    "ViewLedgerDep",
    "get_ensure_user_can_be_deleted_use_case",
]
