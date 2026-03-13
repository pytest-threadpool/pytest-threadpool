"""Class-based methods — call phase runs in parallel threads."""

import threading
import time

import pytest

@pytest.mark.parallel_only
@pytest.mark.parallelizable("children")
class TestParallelExecution:
    """Verify that test methods within a class actually run concurrently."""

    timestamps = {}
    ts_lock = threading.Lock()
    barrier = threading.Barrier(3, timeout=10)

    def _timed_work(self, name):
        start = time.monotonic()
        time.sleep(0.5)
        end = time.monotonic()
        with self.ts_lock:
            self.timestamps[name] = (start, end, threading.current_thread().name)
        # Wait for all 3 to finish, then verify
        self.barrier.wait()
        ts = self.timestamps
        all_starts = [s for s, _, _ in ts.values()]
        all_ends = [e for _, e, _ in ts.values()]
        wall_time = max(all_ends) - min(all_starts)
        assert wall_time < 1.5, (
            f"expected parallel execution (<1.5s), but took {wall_time:.2f}s"
        )
        threads = {t for _, _, t in ts.values()}
        assert len(threads) >= 2, f"expected multiple threads, got {threads}"

    def test_concurrent_a(self):
        self._timed_work("a")

    def test_concurrent_b(self):
        self._timed_work("b")

    def test_concurrent_c(self):
        self._timed_work("c")


class TestSingleMethodClass:
    """A class with only one test — should fall back to sequential."""

    def test_solo(self):
        assert threading.current_thread() is not None
