"""Pytester tests for sequential behavior when no parallel markers are used."""


class TestSequentialExecution:
    """Verify unmarked tests run sequentially even with --freethreaded."""

    def test_unmarked_class_runs_sequentially(self, pytester):
        """Class without parallelizable marker preserves test order."""
        pytester.makepyfile("""
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
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_bare_functions_run_sequentially(self, pytester):
        """Bare module functions run sequentially on one thread."""
        pytester.makepyfile("""
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
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=4)
