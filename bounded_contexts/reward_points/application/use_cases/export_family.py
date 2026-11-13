"""Export a whole family as an archive (ADR-0026).

This is a backup operation, so it returns "everything in the family": members, the
children's ledgers, and the daily bonus commitments. Output is not tailored per viewer,
so who may receive it is restricted up front: **only parents (owner / parent)** may call
it. A child can only see their own ledger (ADR-0009), so they cannot be given an archive
that contains the whole family.

Accounts are not included (``FamilyArchiveDTO``). Even if an archive leaks, nothing in it
can be used to sign in.
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_archive_dto import FamilyArchiveDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_archive_writer import FamilyArchiveWriter


class ExportFamilyUseCase:
    def __init__(self, access: FamilyAccessResolver, writer: FamilyArchiveWriter) -> None:
        self._access = access
        self._writer = writer

    def execute(self, *, family_id: int, account_id: int) -> FamilyArchiveDTO:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        return self._writer.write(family_id)


__all__ = ["ExportFamilyUseCase"]
