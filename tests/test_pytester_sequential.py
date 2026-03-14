"""Tests for sequential behavior when no parallel markers are used."""

import pytest


class TestSequentialExecution:
    """Verify unmarked tests run sequentially even with --freethreaded."""

    def test_unmarked_class_runs_sequentially(self, ftdir):
        """Class without parallelizable marker preserves test order."""
        ftdir.makepyfile("""
            import time

            class TestUnmarked:
                order = []

                def test_first(self):
                    time.sleep(0.05)
                    self.order.append("first")

                def test_second(self):
                    self.order.append("second")

                def test_third(self):
                    self.order.append("third")

            def test_verify():
                assert TestUnmarked.order == ["first", "second", "third"]
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_bare_functions_run_sequentially(self, ftdir):
        """Bare module functions run sequentially on one thread."""
        ftdir.makepyfile("""
            import threading
            from time import sleep

            class _State:
                execution_log = []

            def test_a():
                sleep(0.05)
                _State.execution_log.append(("a", threading.current_thread().name))

            def test_b():
                _State.execution_log.append(("b", threading.current_thread().name))

            def test_c():
                _State.execution_log.append(("c", threading.current_thread().name))

            def test_verify():
                names = [name for name, _ in _State.execution_log]
                assert names == ["a", "b", "c"]
                threads = {t for _, t in _State.execution_log}
                assert len(threads) == 1
            """
        )
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)
