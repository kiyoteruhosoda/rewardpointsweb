"""毎日のボーナスを配る定期実行の組み立て（ADR-0024）。

誰の要求もきっかけにならない処理なので、リクエストの依存関係（``Depends()``）
ではなくここで自前に組み立てる。DB セッションも 1 周ごとに開いて閉じる —
常駐スレッドが 1 本のセッションを持ち続けると、接続が切れた後の 1 周から
ずっと失敗し続ける。

``UNIQUE (ledger_id, idempotency_key)`` があるので、Gunicorn のワーカーが
複数あって同時に走っても台帳に入るのは 1 日 1 行。ワーカーごとに 1 本ずつ
スレッドが立つのはそのまま許している（配る側で 1 本に絞る仕掛けを足すより、
二重に走っても壊れない方に寄せる）。
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

#: 何分おきに日付の変わり目を見に行くか。取りこぼした日は次の周で追いつくので、
#: 細かくしても得られるのは「日付が変わってから届くまでの短さ」だけ
POLL_INTERVAL_SECONDS = 15 * 60


def grant_due_daily_bonuses() -> None:
    """1 周分の付与。自前のセッションで開き、終わりに必ず閉じる。"""
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
    """定期実行を開始する（テスト実行時は何もしない）。"""
    return start_periodic_runner(
        name="daily-bonus",
        interval_seconds=POLL_INTERVAL_SECONDS,
        task=grant_due_daily_bonuses,
    )


def _report(result: GrantedDailyBonuses) -> None:
    """配った結果を残す。何も配らなかった周（ほとんどの周）は黙る。"""
    if result.granted:
        logger.info("daily_bonus_granted", extra={"granted": result.granted})
    if result.skipped:
        # 遡る上限で捨てた日数。黙って切り捨てると「毎日渡している」という
        # 前提だけが残る（上限は DAILY_BONUS_MAX_CATCH_UP_DAYS）
        logger.warning("daily_bonus_catch_up_truncated", extra={"skipped": result.skipped})


__all__ = ["POLL_INTERVAL_SECONDS", "grant_due_daily_bonuses", "start_daily_bonus_grants"]
