"""Single file with parametrized tests — live display must not duplicate file lines."""

import time

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestParams:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_param(self, n):
        time.sleep(0.05 * n)
