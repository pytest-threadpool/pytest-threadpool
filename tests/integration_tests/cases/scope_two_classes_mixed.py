"""Two classes in one module: one parallelizable, one sequential."""

import threading
from typing import ClassVar

import pytest


class TestState:
    parallel_threads: ClassVar[set] = set()
    sequential_threads: ClassVar[set] = set()
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.mark.parallelizable("children")
class TestParallel:
    barrier = threading.Barrier(2, timeout=10)

    def test_a(self):
        with TestState.lock:
            TestState.parallel_threads.add(threading.current_thread().name)
        self.barrier.wait()

    def test_b(self):
        with TestState.lock:
            TestState.parallel_threads.add(threading.current_thread().name)
        self.barrier.wait()


class TestSequential:
    def test_x(self):
        with TestState.lock:
            TestState.sequential_threads.add(threading.current_thread().name)

    def test_y(self):
        with TestState.lock:
            TestState.sequential_threads.add(threading.current_thread().name)


def test_verify():
    # Parallel class used worker threads (at least 2 distinct threads)
    assert len(TestState.parallel_threads) >= 2, (
        f"expected parallel threads, got {TestState.parallel_threads}"
    )
    # Sequential class ran on MainThread only
    assert TestState.sequential_threads == {"MainThread"}, (
        f"expected MainThread only, got {TestState.sequential_threads}"
    )
