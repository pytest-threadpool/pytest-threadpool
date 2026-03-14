"""Pytester tests for class-level parallel execution."""


class TestClassParallel:
    """Verify @parallelizable('children') on classes via isolated subprocess runs."""

    def test_barrier_proves_concurrency(self, pytester):
        """3-party barrier succeeds only if methods run concurrently."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("children")
            class TestConcurrent:
                barrier = threading.Barrier(3, timeout=10)

                def test_a(self):
                    self.barrier.wait()

                def test_b(self):
                    self.barrier.wait()

                def test_c(self):
                    self.barrier.wait()
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_uses_multiple_threads(self, pytester):
        """Verify methods actually run on different threads."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("children")
            class TestThreads:
                barrier = threading.Barrier(3, timeout=10)

                def _work(self):
                    self.barrier.wait()
                    print(f"THREAD:{threading.current_thread().name}")

                def test_a(self):
                    self._work()

                def test_b(self):
                    self._work()

                def test_c(self):
                    self._work()
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "3", "-s")
        result.assert_outcomes(passed=3)
        threads = {l.split("THREAD:")[1] for l in result.outlines if "THREAD:" in l}
        assert len(threads) >= 2, f"expected multiple threads, got {threads}"

    def test_single_method_class(self, pytester):
        """A class with one test falls back to sequential without error."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestSolo:
                def test_only(self):
                    assert True
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=1)
