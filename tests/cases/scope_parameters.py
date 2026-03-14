"""Parametrized variants run concurrently with 'parameters' scope."""

import threading

import pytest


@pytest.mark.parallelizable("parameters")
@pytest.mark.parametrize("v", ["x", "y", "z"])
def test_param(v):
    barrier = test_param._barrier
    barrier.wait()


test_param._barrier = threading.Barrier(3, timeout=10)
