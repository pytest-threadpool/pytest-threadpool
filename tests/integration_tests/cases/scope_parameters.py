"""Parametrized variants run concurrently with 'parameters' scope."""

import threading

import pytest


@pytest.mark.parallelizable("parameters")
class TestParam:
    _barrier = threading.Barrier(3, timeout=10)

    @pytest.mark.parametrize("v", ["x", "y", "z"])
    def test_param(self, v):
        self._barrier.wait()
