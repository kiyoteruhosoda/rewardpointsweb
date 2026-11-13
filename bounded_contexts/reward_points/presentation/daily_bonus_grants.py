"""Wiring for the scheduled job that grants daily bonuses (ADR-0024).

No request triggers this work, so it is wired up here by hand rather than through
request dependencies (``Depends()``). The DB session is opened and closed on every
pass — a long-lived thread holding one session would keep failing from the first
pass after the connection drops.

Thanks to ``UNIQUE (ledger_id, idempotency_key)``, even with several Gunicorn
workers running at once, the ledger gets one row per day. One thread per worker is
allowed as is (we prefer being safe when run twice over adding a mechanism to limit
it to one).
"""

from __future__ import annotations

import logging

from bounded_contexts.reward_points.application.use_cases.grant_due_daily_bonuses import (
    GrantDueDailyBonusesUseCase,
    GrantedDailyBonuses,
)
from bounded_contexts.reward_points.infrastructure.sql_daily_bonus_repository import (
    SqlDailyBonusRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_transaction_repository import (
    SqlPointTransactionRepository,
)
from bounded_contexts.reward_points.presentation.dependencies import resolve_day_boundary
from shared.kernel.database.db import get_session_factory
from shared.kernel.scheduling import PeriodicRunner, start_periodic_runner
from shared.kernel.settings.settings import settings
from shared.kernel.timestamps import utcnow

logger = logging.getLogger(__name__)

#: How often to check for a day change. Missed days are caught up on the next pass,
#: so a shorter interval only shortens the delay after the date changes
POLL_INTERVAL_SECONDS = 15 * 60


def grant_due_daily_bonuses() -> None:
    """One granting pass. Opens its own session and always closes it at the end."""
    session = get_session_factory()()
    try:
        use_case = GrantDueDailyBonusesUseCase(
            bonuses=SqlDailyBonusRepository(session),
            transactions=SqlPointTransactionRepository(session),
            boundary=resolve_day_boundary(),
            max_catch_up_days=settings.daily_bonus_max_catch_up_days,
        )
        result = use_case.execute(now=utcnow())
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    _report(result)


def start_daily_bonus_grants() -> PeriodicRunner | None:
    """Start the scheduled job (does nothing under tests)."""
    return start_periodic_runner(
        name="daily-bonus",
        interval_seconds=POLL_INTERVAL_SECONDS,
        task=grant_due_daily_bonuses,
    )


def _report(result: GrantedDailyBonuses) -> None:
    """Log what was granted. Passes that grant nothing (most of them) stay silent."""
    if result.granted:
        logger.info("daily_bonus_granted", extra={"granted": result.granted})
    if result.skipped:
        # Days dropped by the catch-up limit. Dropping them silently would leave only the
        # false assumption that bonuses go out every day (limit: DAILY_BONUS_MAX_CATCH_UP_DAYS)
        logger.warning("daily_bonus_catch_up_truncated", extra={"skipped": result.skipped})


__all__ = ["POLL_INTERVAL_SECONDS", "grant_due_daily_bonuses", "start_daily_bonus_grants"]
