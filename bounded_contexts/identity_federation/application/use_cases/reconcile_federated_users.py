"""Ask assay again and stop SSO sessions of people who can no longer use the app (periodic reconciliation. ADR-0040).

This is the second stage, picking up what the receiving endpoint (ADR-0032) missed. The scope of what it stops is
the same as the endpoint -- **only sessions started via SSO**; the user itself (local password, passkeys)
is not touched. This template intentionally keeps local accounts (ADR-0035).

⚠ **If the roster cannot be fetched, do nothing.** Do not mix up "the roster cannot be fetched" and
"the roster is empty"
-- mixing them would stop everyone just because assay is having trouble. If it cannot be fetched,
:class:`~bounded_contexts.identity_federation.domain.exceptions.IdentityProviderUnavailableError`
is raised and this job ends without changing anything.

⚠ **Write it so that running it any number of times gives the same result.** The periodic run executes
concurrently once per worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime

from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)
from bounded_contexts.identity_federation.domain.entities.session_revocation import (
    SessionRevocation,
)
from bounded_contexts.identity_federation.domain.repositories.federated_identity_repository import (
    FederatedIdentityRepository,
)
from bounded_contexts.identity_federation.domain.repositories.session_revocation_repository import (
    SessionRevocationRepository,
)
from bounded_contexts.identity_federation.domain.services.roster_gateway import (
    RosterGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.roster import (
    Roster,
    RosterState,
)
from shared.kernel.timestamps import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReconciliationOutcome:
    """What happened in one reconciliation (counts for logging and tests)."""

    checked: int = 0
    #: Number of people newly revoked. ⚠ People already revoked in a previous run are not counted
    #: (the same row is not written).
    revoked: int = 0
    unlinked: int = 0
    #: ⚠ Whether it **held back because everyone came back as `unknown`** (decision 3). When true, nothing was changed.
    held_back: bool = False


@dataclass(frozen=True)
class ReconcileFederatedUsers:
    issuer: str
    identities: FederatedIdentityRepository
    revocations: SessionRevocationRepository
    roster: RosterGateway
    #: Seconds to keep revocation records. Pass **the refresh token lifetime** (same as the endpoint. ADR-0032).
    keep_for_seconds: int

    def execute(self) -> ReconciliationOutcome:
        links = list(self.identities.list_for_issuer(self.issuer))
        if not links:
            return ReconciliationOutcome()
        # ⚠ Ask by name. A list of candidates cannot tell "not present over there (gone)".
        answers = self.roster.fetch(subjects=tuple(link.subject for link in links))
        outcome = ReconciliationOutcome(checked=len(links))
        if _everyone_is_unknown(links, answers):
            # ⚠ A tenant mix-up or an app reassignment also looks like this. Links can only be recreated
            #   by the user's own action (ADR-0036), so stop before removing everyone's.
            logger.warning("sso_reconciliation_everyone_unknown", extra={"checked": len(links)})
            return replace(outcome, held_back=True)
        now = utcnow()
        for link in links:
            outcome = self._apply(link, answers.state_of(link.subject), now=now, outcome=outcome)
        return outcome

    def _apply(
        self,
        link: FederatedIdentity,
        state: RosterState,
        *,
        now: datetime,
        outcome: ReconciliationOutcome,
    ) -> ReconciliationOutcome:
        """Apply the result for one person. ⚠ **Explicitly return the side that is left untouched too.**"""
        if not state.ends_sessions:
            return outcome
        revocation = SessionRevocation.after_reconciliation(
            link,
            now=now,
            keep_for_seconds=self.keep_for_seconds,
        )
        if self.revocations.record(revocation):
            logger.info("sso_sessions_revoked_by_reconciliation", extra={"user_id": link.user_id})
            outcome = replace(outcome, revoked=outcome.revoked + 1)
        if not state.drops_the_link:
            return outcome
        # Not present over there = the link's counterpart no longer exists. Keeping the row would connect to
        # someone else if the same `sub` were reused for another person (it is promised not to be reused,
        # but there is no reason to keep it either).
        # ⚠ Revocation records apply to `(issuer, sub)`, not to the link, so they remain after unlinking.
        self.identities.unlink(link)
        logger.info("sso_identity_unlinked_by_reconciliation", extra={"user_id": link.user_id})
        return replace(outcome, unlinked=outcome.unlinked + 1)


def _everyone_is_unknown(links: list[FederatedIdentity], answers: Roster) -> bool:
    """Whether there are 2 or more links and everyone came back as `unknown` (ADR-0040 decision 3).

    With only one, it cannot be told apart from "that one person is gone", so it is handled normally.
    """
    if len(links) < 2:
        return False
    return all(answers.state_of(link.subject) is RosterState.UNKNOWN for link in links)


__all__ = ["ReconcileFederatedUsers", "ReconciliationOutcome"]
