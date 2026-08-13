"""控えの JSON（Pydantic）と Application 層の DTO を行き来する（ADR-0026）。

入れ子が深いぶん変換も長くなるので、ルーターから外へ出す。ルーター本体は
「ユースケースを 1 回呼んで、1 回変換する」だけに保つ。

向きは 2 つあるが、形は 1 つ。書き出した JSON をそのまま取り込めることが控えの
値打ちなので、応答と本文でスキーマを分けない。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ArchivedDailyBonusDTO,
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    ArchivedTransactionDTO,
    FamilyArchiveDTO,
)
from bounded_contexts.reward_points.presentation.schemas import (
    ArchivedDailyBonusDocument,
    ArchivedLedgerDocument,
    ArchivedMemberDocument,
    ArchivedTransactionDocument,
    FamilyArchiveDocument,
)


def to_document(archive: FamilyArchiveDTO) -> FamilyArchiveDocument:
    return FamilyArchiveDocument(
        format=archive.format,
        version=archive.version,
        exported_at=archive.exported_at,
        family_name=archive.family_name,
        family_rules=archive.family_rules,
        members=[_member_document(member) for member in archive.members],
    )


def to_dto(document: FamilyArchiveDocument) -> FamilyArchiveDTO:
    return FamilyArchiveDTO(
        format=document.format,
        version=document.version,
        exported_at=document.exported_at,
        family_name=document.family_name,
        family_rules=document.family_rules,
        members=tuple(_member_dto(member) for member in document.members),
    )


def _member_document(member: ArchivedMemberDTO) -> ArchivedMemberDocument:
    return ArchivedMemberDocument(
        ref=member.ref,
        display_name=member.display_name,
        role=member.role,
        ledger=None if member.ledger is None else _ledger_document(member.ledger),
    )


def _member_dto(member: ArchivedMemberDocument) -> ArchivedMemberDTO:
    return ArchivedMemberDTO(
        ref=member.ref,
        display_name=member.display_name,
        role=member.role,
        ledger=None if member.ledger is None else _ledger_dto(member.ledger),
    )


def _ledger_document(ledger: ArchivedLedgerDTO) -> ArchivedLedgerDocument:
    bonus = ledger.daily_bonus
    return ArchivedLedgerDocument(
        transactions=[_transaction_document(entry) for entry in ledger.transactions],
        daily_bonus=(
            None
            if bonus is None
            else ArchivedDailyBonusDocument(
                amount=bonus.amount,
                reason=bonus.reason,
                starts_on=bonus.starts_on,
                granted_through=bonus.granted_through,
            )
        ),
    )


def _ledger_dto(ledger: ArchivedLedgerDocument) -> ArchivedLedgerDTO:
    bonus = ledger.daily_bonus
    return ArchivedLedgerDTO(
        transactions=tuple(_transaction_dto(entry) for entry in ledger.transactions),
        daily_bonus=(
            None
            if bonus is None
            else ArchivedDailyBonusDTO(
                amount=bonus.amount,
                reason=bonus.reason,
                starts_on=bonus.starts_on,
                granted_through=bonus.granted_through,
            )
        ),
    )


def _transaction_document(entry: ArchivedTransactionDTO) -> ArchivedTransactionDocument:
    return ArchivedTransactionDocument(
        ref=entry.ref,
        amount=entry.amount,
        reason=entry.reason,
        occurred_at=entry.occurred_at,
        granted_by=entry.granted_by,
        reverses=entry.reverses,
        corrects=entry.corrects,
    )


def _transaction_dto(entry: ArchivedTransactionDocument) -> ArchivedTransactionDTO:
    return ArchivedTransactionDTO(
        ref=entry.ref,
        amount=entry.amount,
        reason=entry.reason,
        occurred_at=entry.occurred_at,
        granted_by=entry.granted_by,
        reverses=entry.reverses,
        corrects=entry.corrects,
    )


__all__ = ["to_document", "to_dto"]
