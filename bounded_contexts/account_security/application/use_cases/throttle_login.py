"""Count login failures per identifier and refuse for a while once over the limit (ADR-0055).

Use it in 3 steps: :meth:`require_allowed` **before trying**, :meth:`record_attempt` **when there was an attempt
to count**, and :meth:`record_success` **when it succeeded**.

The unit counted is the identifier that was sent, regardless of whether it exists. Counting only existing ones
would reveal existence by whether the request is refused.
"""

from __future__ import annotations

from datetime import datetime

from bounded_contexts.account_security.domain.entities.login_attempts import (
    LoginAttempts,
    ThrottlePolicy,
)
from bounded_contexts.account_security.domain.exceptions import TooManyAttemptsError
from bounded_contexts.account_security.domain.repositories.login_attempt_repository import (
    LoginAttemptRepository,
)


def normalize_identifier(identifier: str) -> str:
    """Keep case and surrounding whitespace from producing different identifiers."""
    return identifier.strip().lower()


class ThrottleLogin:
    def __init__(self, repository: LoginAttemptRepository, policy: ThrottlePolicy) -> None:
        self._repository = repository
        self._policy = policy

    def require_allowed(self, purpose: str, identifier: str, now: datetime) -> None:
        """:class:`TooManyAttemptsError` while refusing."""
        if not self._policy.enabled:
            return
        retry_after = self._load(purpose, identifier).retry_after(now)
        if retry_after is not None:
            raise TooManyAttemptsError(retry_after_seconds=max(int(retry_after.total_seconds()), 1))

    def record_attempt(self, purpose: str, identifier: str, now: datetime) -> bool:
        """Count once. ``True`` **if this one attempt started the refusal** (to record it in the audit log).

        Login counts failures; a reset request counts successes too (even a success sends
        an email to the target, so without counting, the inbox could be flooded).
        """
        if not self._policy.enabled:
            return False
        before = self._load(purpose, identifier)
        after = before.after_failure(now, self._policy)
        self._repository.save(after, now, self._policy)
        return after.locked_until is not None and before.retry_after(now) is None

    def record_success(self, purpose: str, identifier: str) -> None:
        """Entered correctly. Earlier failures were typos, so forget them."""
        if not self._policy.enabled:
            return
        self._repository.forget(purpose, normalize_identifier(identifier))

    def _load(self, purpose: str, identifier: str) -> LoginAttempts:
        return self._repository.get(purpose, normalize_identifier(identifier))


__all__ = ["ThrottleLogin", "normalize_identifier"]
