"""Tests for thread-safe shared state under parallel execution."""

import pytest


class TestSharedStateUnderParallel:
    """Verify thread-safe dict/counter operations with parallel children."""

    def test_thread_safe_dict_mutation(self, ftdir):
        """Concurrent dict writes from parallel methods are consistent."""
        ftdir.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestDict:
                shared = {}

                def _write(self, key, base, n=1000):
                    for i in range(n):
                        self.shared[f"{key}_{i}"] = base + i

                def test_a(self):
                    self._write("a", 0)

                def test_b(self):
                    self._write("b", 10_000)

                def test_c(self):
                    self._write("c", 20_000)

            def test_verify():
                d = TestDict.shared
                for prefix, base in [("a", 0), ("b", 10_000), ("c", 20_000)]:
                    for i in range(1000):
                        assert f"{prefix}_{i}" in d
                        assert d[f"{prefix}_{i}"] == base + i
        """)
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=4)

    def test_lock_free_counter(self, ftdir):
        """Each thread counts independently, results are correct."""
        ftdir.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestCounter:
                results = {}

                def _count(self, name, n=50_000):
                    total = 0
                    for _ in range(n):
                        total += 1
                    self.results[name] = total

                def test_a(self):
                    self._count("a")

                def test_b(self):
                    self._count("b")

                def test_c(self):
                    self._count("c")

            def test_verify():
                for name in ("a", "b", "c"):
                    assert TestCounter.results[name] == 50_000
        """)
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=4)

    def test_barrier_sync_proves_concurrency(self, ftdir):
        """Two-phase barrier proves tests truly run concurrently."""
        ftdir.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("children")
            class TestBarrier:
                barrier = threading.Barrier(3, timeout=10)
                verify_barrier = threading.Barrier(3, timeout=10)
                arrived = {}

                def _arrive(self, name):
                    self.barrier.wait()
                    self.arrived[name] = True
                    self.verify_barrier.wait()
                    assert self.arrived == {"a": True, "b": True, "c": True}

                def test_a(self):
                    self._arrive("a")

                def test_b(self):
                    self._arrive("b")

                def test_c(self):
                    self._arrive("c")
        """)
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)
