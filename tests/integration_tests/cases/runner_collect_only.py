"""Parallel-marked tests work with --collect-only."""

import threading

import pytest


@pytest.mark.parallelizable("children")
class TestCollectOnly:
    barrier = threading.Barrier(2, timeout=10)

    def test_a(self):
        self.barrier.wait()

    def test_b(self):
        self.barrier.wait()
