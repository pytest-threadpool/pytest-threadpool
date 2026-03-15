"""Module-level pytestmark parallelizable('children') with barrier."""

import threading

import pytest

pytestmark = pytest.mark.parallelizable("children")


class _State:
    barrier = threading.Barrier(3, timeout=10)


def test_a():
    _State.barrier.wait()


def test_b():
    _State.barrier.wait()


def test_c():
    _State.barrier.wait()
