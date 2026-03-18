"""Tests that print to stdout during parallel execution must not corrupt display."""

import time

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestWithPrint:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_param(self, n):
        print(f"output from test {n}")
        time.sleep(0.05 * n)
