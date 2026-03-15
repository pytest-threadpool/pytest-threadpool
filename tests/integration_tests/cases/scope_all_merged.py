"""'all' merges plain methods and parametrized variants into one batch."""

import threading

import pytest


@pytest.mark.parallelizable("all")
class TestAll:
    barrier = threading.Barrier(5, timeout=10)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_param(self, n):
        self.barrier.wait()

    def test_plain_a(self):
        self.barrier.wait()

    def test_plain_b(self):
        self.barrier.wait()
