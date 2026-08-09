"""決まった間隔で処理を回す常駐スレッド。

日付が変わったことに気付いてポイントを配る（ADR-0024）といった、誰の要求も
きっかけにならない処理のための入口。時計を持つ別のコンテナや外部の cron を
足さずに済ませるための最小の仕組みで、``RestartWatcher`` と同じ形にしてある。

守っている約束は 2 つ。

- **止まらない。** 1 周が例外で終わってもスレッドは生き続ける（DB の一時障害で
  以後の付与が永久に止まると、誰にも気付かれないまま日が過ぎる）。
- **すぐ 1 周する。** 起動直後に 1 回走ってから間隔を待つ。止まっていたあいだの
  取りこぼしを、次の間隔まで待たずに片付けられる。

**この仕組み自体は「1 回だけ実行される」ことを保証しない。** Gunicorn の
ワーカーは複数あり、それぞれがこのスレッドを持つ。同じ処理が同時に走っても
壊れないこと（冪等であること）は、渡す処理の側の責任。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

_runners: list[PeriodicRunner] = []


class PeriodicRunner:
    def __init__(self, *, name: str, interval_seconds: float, task: Callable[[], None]) -> None:
        self._name = name
        self._interval_seconds = interval_seconds
        self._task = task
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name=f"periodic-{self._name}", daemon=True)
        self._thread.start()
        logger.info(
            "定期実行を開始しました: name=%s interval=%.0fs",
            self._name,
            self._interval_seconds,
            extra={"event": "scheduling.start"},
        )

    def stop(self) -> None:
        self._stop_event.set()

    def run_once(self) -> None:
        """1 周だけ回す。例外はここで止め、記録だけ残す。"""
        try:
            self._task()
        except Exception:
            logger.warning(
                "定期実行が失敗しました: name=%s",
                self._name,
                exc_info=True,
                extra={"event": "scheduling.failed"},
            )

    def _run(self) -> None:
        self.run_once()
        while not self._stop_event.wait(self._interval_seconds):
            self.run_once()


def start_periodic_runner(*, name: str, interval_seconds: float, task: Callable[[], None]) -> PeriodicRunner | None:
    """定期実行を開始する。テスト実行時（``TESTING``）は何もしない。

    テストで走らせないのは、``TestClient`` が起動のたびに別スレッドから DB を
    触りに行くのを避けるため。処理そのものはユースケースを直接呼んで検証する。
    """
    from shared.kernel.settings.settings import settings

    if settings.testing:
        return None

    runner = PeriodicRunner(name=name, interval_seconds=interval_seconds, task=task)
    runner.start()
    _runners.append(runner)
    return runner


def stop_periodic_runners() -> None:
    """起動済みの定期実行を止める（プロセス終了時・テスト後始末用）。"""
    for runner in _runners:
        runner.stop()
    _runners.clear()


__all__ = ["PeriodicRunner", "start_periodic_runner", "stop_periodic_runners"]
