"""Assembly of periodic reconciliation (ADR-0040).

Wiring that connects the use case (Application) with the implementations (Infrastructure).
Infrastructure cannot import Application, so the outermost layer does the assembly.

**Settings are read on every run.** Once SSO is enabled and ``MACHINE_CLIENT_ID`` is set, it takes effect from
the next cycle.

⚠ **Do not decide whether to run based on the application identity.** If SSO is usable and the service account has a
`client_id`, it asks every cycle, and until assay binds this service account as the application's identity it gets 403
-- that is logged as one info line "not bound", and it ends without changing anything.

⚠ **Opens its own session.** It runs outside the request flow, so the ``get_db``
session (opened and closed per request) cannot be used.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from bounded_contexts.identity_federation.application.use_cases.reconcile_federated_users import (
    ReconcileFederatedUsers,
    ReconciliationOutcome,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityProviderUnavailableError,
    MachineNotBoundToApplicationError,
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.services.roster_gateway import (
    RosterGateway,
)
from bounded_contexts.identity_federation.infrastructure.httpx_roster_gateway import (
    HttpxRosterGateway,
)
from bounded_contexts.identity_federation.infrastructure.sql_federated_identity_repository import (
    SqlFederatedIdentityRepository,
)
from bounded_contexts.identity_federation.infrastructure.sql_session_revocation_repository import (
    SqlSessionRevocationRepository,
)
from bounded_contexts.identity_federation.presentation import dependencies
from shared.kernel.database.db import get_engine
from shared.kernel.scheduling import PeriodicRunner, start_periodic_runner
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

RUNNER_NAME = "sso-reconciliation"

# Reconciliation interval. ⚠ **Not a setting.** The interval is read only once at startup, so exposing it on screen
# would make it "a setting that has no effect when changed". The main path for catching stopped people quickly is the
# receiver (ADR-0032); this is the second stage that catches what it missed, so one hour is enough.
RECONCILE_INTERVAL_SECONDS = 60 * 60

#: One per process. ⚠ **Reuses the token across cycles**, so do not create one on every call.
_ROSTER: RosterGateway = HttpxRosterGateway()

#: Failures where skipping changes nothing. ⚠ **Do not read "could not look up" as "empty"** (ADR-0040 decision 2).
_SKIPPABLE = (IdentityProviderUnavailableError, SsoNotConfiguredError)


def reconcile_federated_users_once(roster: RosterGateway | None = None) -> None:
    """Reconcile once according to the current settings.

    ⚠ **If assay cannot be asked, end without changing anything** (do not mix "empty" with "cannot look up").
    """
    provider = dependencies.identity_provider()
    if not settings.machine_client_id or provider is None or not provider.is_usable:
        # If settings say not to reconcile, do not even open a session.
        return
    session = sessionmaker(bind=get_engine())()
    try:
        outcome = _reconcile(session, provider.issuer, roster or _ROSTER)
    finally:
        session.close()
    if outcome is not None:
        logger.info(
            "sso_reconciliation_finished",
            extra={
                "checked": outcome.checked,
                "revoked": outcome.revoked,
                "unlinked": outcome.unlinked,
                "held_back": outcome.held_back,
            },
        )


def _reconcile(session: Session, issuer: str, roster: RosterGateway) -> ReconciliationOutcome | None:
    """Reconcile and commit. If skipped, roll back and return ``None``."""
    try:
        outcome = ReconcileFederatedUsers(
            # ⚠ Look up with the issuer from **the same source** as when linking. Off by one character and
            #   nothing matches, ending with "no anomalies" without checking anything.
            issuer=issuer,
            identities=SqlFederatedIdentityRepository(session),
            revocations=SqlSessionRevocationRepository(session),
            roster=roster,
            keep_for_seconds=settings.refresh_token_expires_seconds,
        ).execute()
        session.commit()
    except MachineNotBoundToApplicationError:
        session.rollback()
        # ⚠ Waiting for setup, not an outage. It comes every hour until bound, so it is not a warning.
        logger.info("sso_reconciliation_not_bound")
        return None
    except _SKIPPABLE as error:
        session.rollback()
        logger.warning("sso_reconciliation_skipped", extra={"reason": type(error).__name__})
        return None
    except IntegrityError:
        # Another worker wrote the same revocation in the same cycle (`jti` is deterministic, so the content
        # is the same).
        session.rollback()
        logger.info("sso_reconciliation_raced")
        return None
    return outcome


def start_sso_reconciliation() -> PeriodicRunner | None:
    """Start periodic reconciliation (called from process startup; does nothing during tests)."""
    return start_periodic_runner(
        name=RUNNER_NAME,
        interval_seconds=RECONCILE_INTERVAL_SECONDS,
        task=reconcile_federated_users_once,
    )


__all__ = [
    "RECONCILE_INTERVAL_SECONDS",
    "RUNNER_NAME",
    "reconcile_federated_users_once",
    "start_sso_reconciliation",
]
