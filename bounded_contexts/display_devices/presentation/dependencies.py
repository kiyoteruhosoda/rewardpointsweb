"""表示端末コンテキストの依存の組み立て（``Depends()`` 用）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from bounded_contexts.display_devices.application.use_cases.open_display_session import (
    DescribeDisplayCredentialsUseCase,
    OpenDisplaySessionUseCase,
)
from bounded_contexts.display_devices.application.use_cases.pair_display import (
    ApprovePairingUseCase,
    ClaimPairingUseCase,
    StartPairingUseCase,
)
from bounded_contexts.display_devices.infrastructure.sql_display_repositories import (
    SqlDisplayCredentialRepository,
    SqlDisplayPairingRepository,
)
from shared.kernel.database.session import get_db

DbDep = Annotated[Session, Depends(get_db)]


def get_pairing_repository(db: DbDep) -> SqlDisplayPairingRepository:
    return SqlDisplayPairingRepository(db)


def get_credential_repository(db: DbDep) -> SqlDisplayCredentialRepository:
    return SqlDisplayCredentialRepository(db)


PairingRepoDep = Annotated[SqlDisplayPairingRepository, Depends(get_pairing_repository)]
CredentialRepoDep = Annotated[SqlDisplayCredentialRepository, Depends(get_credential_repository)]


def get_start_pairing_use_case(pairings: PairingRepoDep) -> StartPairingUseCase:
    return StartPairingUseCase(pairings)


def get_approve_pairing_use_case(pairings: PairingRepoDep) -> ApprovePairingUseCase:
    return ApprovePairingUseCase(pairings)


def get_claim_pairing_use_case(pairings: PairingRepoDep, credentials: CredentialRepoDep) -> ClaimPairingUseCase:
    return ClaimPairingUseCase(pairings, credentials)


def get_open_display_session_use_case(credentials: CredentialRepoDep) -> OpenDisplaySessionUseCase:
    return OpenDisplaySessionUseCase(credentials)


def get_describe_display_credentials_use_case(credentials: CredentialRepoDep) -> DescribeDisplayCredentialsUseCase:
    return DescribeDisplayCredentialsUseCase(credentials)


StartPairingDep = Annotated[StartPairingUseCase, Depends(get_start_pairing_use_case)]
ApprovePairingDep = Annotated[ApprovePairingUseCase, Depends(get_approve_pairing_use_case)]
ClaimPairingDep = Annotated[ClaimPairingUseCase, Depends(get_claim_pairing_use_case)]
OpenDisplaySessionDep = Annotated[OpenDisplaySessionUseCase, Depends(get_open_display_session_use_case)]
DescribeDisplayCredentialsDep = Annotated[
    DescribeDisplayCredentialsUseCase, Depends(get_describe_display_credentials_use_case)
]


__all__ = [
    "ApprovePairingDep",
    "ClaimPairingDep",
    "DescribeDisplayCredentialsDep",
    "OpenDisplaySessionDep",
    "StartPairingDep",
]
