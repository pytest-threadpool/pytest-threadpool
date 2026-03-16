"""Single file with parametrized tests — live display must not duplicate file lines."""

import time

import pytest


@pytest.mark.parallelizable("children")
class TestParams:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_param(self, n):
        time.sleep(0.05 * n)
