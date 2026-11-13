"""Whether a user asserted by the IdP may be linked to a user of this app.

This decides only two things: "is this someone we may accept" and "may they be merged into an existing user".
A first-time user with nothing to merge into is welcomed with a new account (ADR-0041), but **who may get one
is not decided here** -- assay's application assignments decide that, and people without an assignment
do not come back holding a code.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoEmailNotAllowedError,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)


@dataclass(frozen=True)
class AccountLinkingPolicy:
    #: ⚠ **Default is not to merge** (ADR-0033). The condition ``email_verified`` in assay means
    #: "a tenant admin claims so", not proof by the person themselves.
    #: ⚠ Even when closed, **if an account with the same email exists, refuse instead of creating one** (ADR-0041).
    #: The person signs in to that account and links it (ADR-0036).
    link_by_email: bool = False
    allowed_email_domains: tuple[str, ...] = ()

    def ensure_accepted(self, user: FederatedUser) -> None:
        """Check whether this is someone we may accept. If not, :class:`SsoEmailNotAllowedError`.

        If no domains are restricted (empty), anyone is accepted. Restricting the audience on the IdP
        side is the usual setup, so by default no further restriction is layered here.
        """
        if not self.allowed_email_domains:
            return
        if user.email_domain not in {domain.lower().lstrip("@") for domain in self.allowed_email_domains}:
            raise SsoEmailNotAllowedError

    def may_link(self, user: FederatedUser) -> bool:
        """Whether they may be merged into an existing user.

        **Default is not to merge** (ADR-0033). Even when enabled, **only for a verified email
        address** -- merging on an address the IdP has not verified would let anyone get into
        someone else's account just by claiming their address.

        ⚠ **The meaning of ``email_verified`` differs per IdP.** In our own idp (assay)
        the only path that sets it true is the self-registration confirmation email, and **an email
        change by an admin keeps this value**. In other words it means not "the person proved ownership" but
        **"a tenant admin claims so"**. If enabling this, also check how the value gets set in the
        connected IdP.
        """
        return self.link_by_email and user.email_verified


__all__ = ["AccountLinkingPolicy"]
