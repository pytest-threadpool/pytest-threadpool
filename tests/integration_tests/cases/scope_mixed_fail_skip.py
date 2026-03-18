"""Sequential not_parallelizable methods that fail or skip alongside parallel methods."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import not_parallelizable, parallelizable


class TestState:
    parallel_log: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@parallelizable("children")
class TestMixedFailSkip:
    barrier = threading.Barrier(2, timeout=10)

    def test_parallel_a(self):
        self.barrier.wait()
        with TestState.lock:
            TestState.parallel_log.append("a")

    def test_parallel_b(self):
        self.barrier.wait()
        with TestState.lock:
            TestState.parallel_log.append("b")

    @not_parallelizable
    def test_seq_fail(self):
        pytest.fail("intentional failure")

    @not_parallelizable
    def test_seq_skip(self):
        pytest.skip("intentional skip")


def test_verify():
    assert set(TestState.parallel_log) == {"a", "b"}
