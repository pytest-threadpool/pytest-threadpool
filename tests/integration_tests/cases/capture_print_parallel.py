"""Parallel tests that print to stdout — used to verify stream proxy behavior."""

import time

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestPrintsInParallel:
    @pytest.mark.parametrize("n", range(4))
    def test_print_worker(self, n):
        print(f"WORKER_OUTPUT_{n}")
        time.sleep(0.02)
