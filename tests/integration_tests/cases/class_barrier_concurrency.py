"""3-party barrier — succeeds only if methods run concurrently."""

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
