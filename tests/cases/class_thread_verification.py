"""Barrier sync + thread name capture to prove multi-threading."""

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
