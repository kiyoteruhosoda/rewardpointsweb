"""The resident thread for periodic execution (``shared.kernel.scheduling``).

What we want to guarantee is "one failed round does not stop it". If it stopped, later grants
would never happen again without anyone noticing. To avoid waiting real time,
this calls :meth:`PeriodicRunner.run_once` directly without starting the thread.
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
        raise RuntimeError("DB unreachable")

    runner = PeriodicRunner(name="test", interval_seconds=60, task=explode)

    with caplog.at_level(logging.WARNING):
        runner.run_once()

    assert "test" in caplog.text


def test_a_failure_does_not_stop_later_rounds() -> None:
    """A single failure does not stop later rounds."""
    calls: list[str] = []

    def flaky() -> None:
        calls.append("called")
        if len(calls) == 1:
            raise RuntimeError("temporary failure")

    runner = PeriodicRunner(name="test", interval_seconds=60, task=flaky)

    runner.run_once()
    runner.run_once()

    assert calls == ["called", "called"]


def test_it_does_not_start_during_tests() -> None:
    """No thread is started under ``TESTING`` (do not let another thread touch the DB)."""
    started = start_periodic_runner(name="test", interval_seconds=60, task=lambda: None)

    assert started is None
    stop_periodic_runners()
