"""Module-level pytestmark parallelizable('children') with barrier."""

import threading

from pytest_threadpool import parallelizable

pytestmark = parallelizable("children")


class _State:
    barrier = threading.Barrier(3, timeout=10)


def test_a():
    _State.barrier.wait()


def test_b():
    _State.barrier.wait()


def test_c():
    _State.barrier.wait()
