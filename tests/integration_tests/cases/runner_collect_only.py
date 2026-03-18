"""Parallel-marked tests work with --collect-only."""

import threading

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestCollectOnly:
    barrier = threading.Barrier(2, timeout=10)

    def test_a(self):
        self.barrier.wait()

    def test_b(self):
        self.barrier.wait()
