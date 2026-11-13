"""Password reset (token issuance, sending mail, setting a new password).

Tokens are never stored in plain text; only their SHA-256 hash is stored.

Requests are identified by **user name**. Email addresses became optional, so "the owner of that
address" cannot be the starting point (ADR-0011). The response is one of the two
:class:`ResetOutcome` values and **does not vary with whether the account exists**.
Child accounts without an email address get the same response as a non-existent user name
(so outsiders cannot check whether a child's user name exists; task #733).
So nobody waits for mail that will never arrive, the UI always adds "accounts without an email
address should ask a parent for a temporary password".

There is also ``MAIL_UNAVAILABLE``. Replying "sent" while ``MAIL_ENABLED`` is disabled or SMTP
is down would leave people waiting for mail that never arrives, effectively removing the way to
recover from being unable to log in. Whether mail can be sent does not depend on the user, so a
non-existent user name gets the same response and existence does not leak. Whether SMTP is
reachable is unknown until sending is tried, so requests with nowhere to send (unknown, child,
SSO-only accounts) also check SMTP reachability before deciding the response (task #768;
previously, an adult user name's existence could be probed from outside only during SMTP outages).

And the issued link is **always written to the log**, to keep a path for the operator to hand it
to the person even when mail does not arrive. Anyone who can read the log can take over the
account with that link, so log access must be limited to administrators.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import timedelta
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.email_sender.application.send_email import SendEmail
from bounded_contexts.email_sender.domain.email_message import EmailMessage
from bounded_contexts.email_sender.domain.email_sender import (
    EmailSendingDisabledError,
    IEmailSender,
)
from bounded_contexts.email_sender.infrastructure.smtp_email_sender import (
    SmtpEmailSender,
)
from shared.domain.auth.username import Username
from shared.infrastructure.models import PasswordResetToken, User
from shared.infrastructure.models.base import utcnow
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ResetOutcome(Enum):
    """Outcome of a request."""

    #: Sent the reset link (or the user name does not exist / has no email address)
    ACCEPTED = "accepted"
    #: Mail cannot be sent (``MAIL_ENABLED`` is disabled, or SMTP is unreachable).
    #: Waiting would not help, so direct the user to a temporary password from a parent
    MAIL_UNAVAILABLE = "mail_unavailable"


class PasswordResetService:
    def __init__(self, sender: IEmailSender | None = None) -> None:
        self._sender = sender or SmtpEmailSender()

    def request_reset(self, session: Session, username: str) -> ResetOutcome:
        """Issue a reset token, write it to the log, then send the mail.

        If the user does not exist, silently return "``ACCEPTED`` if mail can be sent" (no leak
        of existence). When there is no way to send or SMTP is unreachable, ``MAIL_UNAVAILABLE``
        is returned regardless of existence, so existence does not leak here either.
        """
        user = self._find(session, username)
        if user is None or not user.is_active:
            logger.info("password_reset_requested_unknown_account")
            # Match the response for existing accounts (decided only by whether mail can be sent)
            return self._outcome_without_sending()
        if not user.has_local_password:
            # ⚠ **A reset must not create local authentication** (ADR-0034). Letting a user with no
            # password set a new one here would silently break "this user can only sign in via
            # SSO". If they should have one, an administrator sets it explicitly.
            # The response is the same as for a non-existent user (no leak of existence).
            logger.info("password_reset_requested_without_local_password")
            return self._outcome_without_sending()
        if user.email is None:
            # Nowhere to send (a child; recovery is a temporary password from a parent. ADR-0011).
            # The response is the same as for a non-existent user — otherwise outsiders could check
            # whether a child's user name exists (task #733). The UI always explains asking a parent
            logger.info("password_reset_requested_without_email")
            return self._outcome_without_sending()

        link = self._issue_link(session, user)
        # Always log the link so the operator can hand it to the person even when mail does not
        # arrive (MAIL_ENABLED disabled, SMTP outage). Anyone who can read the log can take over
        # the account with this link, so log access must be limited to administrators.
        logger.warning("password_reset_link_issued: %s", link)

        try:
            SendEmail(self._sender).execute(
                EmailMessage(
                    to=user.email,
                    subject="Password reset",
                    body=(
                        "A password reset was requested for your account.\n"
                        f"Open the following link to set a new password:\n{link}\n\n"
                        "If you did not request this, you can ignore this mail."
                    ),
                )
            )
        except EmailSendingDisabledError:
            # MAIL_ENABLED is disabled. The link is in the log, so the operator can hand it over
            logger.warning("password_reset_unavailable: mail_disabled")
            return ResetOutcome.MAIL_UNAVAILABLE
        except (OSError, smtplib.SMTPException):
            # SMTP is unreachable. This used to be a 500, shown to the user as a failure with no
            # clear cause. Return something that lets the UI point to a way to recover
            logger.exception("password_reset_unavailable: mail_send_failed")
            return ResetOutcome.MAIL_UNAVAILABLE
        return ResetOutcome.ACCEPTED

    def _outcome_without_sending(self) -> ResetOutcome:
        """Response for a request with nowhere to send. Decided by the same conditions as sending to a real adult.

        A request for a real adult tries SMTP and becomes ``MAIL_UNAVAILABLE`` if it fails.
        Unless SMTP reachability is checked the same way when there is nowhere to send, the
        responses would differ only during outages and leak existence (task #768).
        """
        if not settings.mail_enabled:
            return ResetOutcome.MAIL_UNAVAILABLE
        try:
            self._sender.check_reachable()
        except (OSError, smtplib.SMTPException):
            logger.warning("password_reset_unavailable: mail_unreachable", exc_info=True)
            return ResetOutcome.MAIL_UNAVAILABLE
        return ResetOutcome.ACCEPTED

    @staticmethod
    def _issue_link(session: Session, user: User) -> str:
        """Issue one token and build the URL of the reset screen."""
        token = secrets.token_urlsafe(32)
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_token(token),
                expires_at=utcnow() + timedelta(seconds=settings.password_reset_token_ttl_seconds),
            )
        )
        session.flush()
        base_url = settings.app_base_url.rstrip("/")
        return f"{base_url}/reset-password?token={token}"

    @staticmethod
    def _find(session: Session, username: str) -> User | None:
        try:
            identifier = Username(username).value
        except ValueError:
            return None
        return session.scalar(select(User).where(User.username == identifier))

    def reset(self, session: Session, token: str, new_password: str) -> bool:
        """Verify the token and update the password. True on success."""
        from werkzeug.security import generate_password_hash

        row = session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token)))
        if row is None or row.used_at is not None or row.expires_at < utcnow():
            return False
        user = session.get(User, row.user_id)
        if user is None or not user.is_active:
            return False
        if not user.has_local_password:
            # The password was taken away after issuance (ADR-0034). Refuse even if the token
            # is still valid.
            return False
        user.password_hash = generate_password_hash(new_password)
        # The person can reset via mail even while on a temporary password issued by a parent.
        # Leaving the expiry would make the new password count as expired too.
        user.must_change_password = False
        user.temporary_password_expires_at = None
        row.used_at = utcnow()
        session.flush()
        return True


__all__ = ["PasswordResetService", "ResetOutcome"]
