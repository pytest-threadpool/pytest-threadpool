"""Verify collected count matches actual test count (not inflated by cloning)."""

import threading

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestExactCount:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self):
        self.barrier.wait()

    def test_b(self):
        self.barrier.wait()

    def test_c(self):
        self.barrier.wait()


def test_standalone():
    assert True
