"""Thread-safe shared state: dict mutation across parallel threads."""

import threading

import pytest


class TestThreadSafeDict:
    """Mutate a shared dict from multiple threads and verify consistency."""

    shared = {}
    lock = threading.Lock()

    def _write(self, key, value, iterations=1000):
        for i in range(iterations):
            with self.lock:
                self.shared[f"{key}_{i}"] = value + i

    def test_writer_a(self):
        self._write("a", 0)

    def test_writer_b(self):
        self._write("b", 10_000)

    def test_writer_c(self):
        self._write("c", 20_000)


def test_thread_safe_dict_verify():
    """Runs after TestThreadSafeDict (sequential bare function)."""
    d = TestThreadSafeDict.shared
    for prefix, base in [("a", 0), ("b", 10_000), ("c", 20_000)]:
        for i in range(1000):
            key = f"{prefix}_{i}"
            assert key in d, f"missing key {key}"
            assert d[key] == base + i


class TestLockFreeCounter:
    """Concurrent local increments — each thread has its own counter."""

    results = {}
    results_lock = threading.Lock()

    def _count(self, name, n=50_000):
        total = 0
        for _ in range(n):
            total += 1
        with self.results_lock:
            self.results[name] = total

    def test_counter_a(self):
        self._count("a")

    def test_counter_b(self):
        self._count("b")

    def test_counter_c(self):
        self._count("c")


def test_lock_free_counter_verify():
    """Runs after TestLockFreeCounter (sequential bare function)."""
    for name in ("a", "b", "c"):
        assert TestLockFreeCounter.results.get(name) == 50_000, (
            f"counter {name} = {TestLockFreeCounter.results.get(name)}"
        )


@pytest.mark.parallel_only
class TestBarrierSync:
    """Use a barrier to prove tests truly run concurrently."""

    barrier = threading.Barrier(3, timeout=5)
    verify_barrier = threading.Barrier(3, timeout=5)
    arrived = {}
    arrived_lock = threading.Lock()

    def _arrive_and_verify(self, name):
        # All three must reach the barrier within timeout or it fails
        self.barrier.wait()
        with self.arrived_lock:
            self.arrived[name] = True
        # Second barrier: ensure all have written before verifying
        self.verify_barrier.wait()
        assert self.arrived == {"a": True, "b": True, "c": True}

    def test_sync_a(self):
        self._arrive_and_verify("a")

    def test_sync_b(self):
        self._arrive_and_verify("b")

    def test_sync_c(self):
        self._arrive_and_verify("c")
