"""定期実行の常駐スレッド（``shared.kernel.scheduling``）。

守らせたいのは「1 周が失敗しても止まらない」こと。止まると、以後の付与が
誰にも気付かれないまま永久に行われなくなる。実時間を待たずに済ませるため、
スレッドを起こさず :meth:`PeriodicRunner.run_once` を直接呼んで確かめる。
"""

from __future__ import annotations

import logging

import pytest

from shared.kernel.scheduling import PeriodicRunner, start_periodic_runner, stop_periodic_runners


def test_a_round_runs_the_task() -> None:
    calls: list[int] = []
    runner = PeriodicRunner(name="test", interval_seconds=60, task=lambda: calls.append(1))

    runner.run_once()
    runner.run_once()

    assert calls == [1, 1]


def test_a_failing_round_is_swallowed_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    def explode() -> None:
        raise RuntimeError("DB へ届かない")

    runner = PeriodicRunner(name="test", interval_seconds=60, task=explode)

    with caplog.at_level(logging.WARNING):
        runner.run_once()

    assert "test" in caplog.text


def test_a_failure_does_not_stop_later_rounds() -> None:
    """1 度の失敗で以後の周が止まらないこと。"""
    calls: list[str] = []

    def flaky() -> None:
        calls.append("called")
        if len(calls) == 1:
            raise RuntimeError("一時的な失敗")

    runner = PeriodicRunner(name="test", interval_seconds=60, task=flaky)

    runner.run_once()
    runner.run_once()

    assert calls == ["called", "called"]


def test_it_does_not_start_during_tests() -> None:
    """``TESTING`` ではスレッドを立てない（別スレッドから DB を触らせない）。"""
    started = start_periodic_runner(name="test", interval_seconds=60, task=lambda: None)

    assert started is None
    stop_periodic_runners()
