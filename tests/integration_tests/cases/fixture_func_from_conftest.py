"""Function-scoped fixtures from a same-directory conftest must be cloned per-item."""

import threading
from typing import ClassVar

import pytest


class TestState:
    values: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.mark.parallelizable("children")
class TestConftestFixture:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, conftest_resource):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["a"] = conftest_resource

    def test_b(self, conftest_resource):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["b"] = conftest_resource

    def test_c(self, conftest_resource):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["c"] = conftest_resource


def test_verify():
    # Each test must have received its own fixture instance
    assert TestState.values["a"] == "conftest_test_a"
    assert TestState.values["b"] == "conftest_test_b"
    assert TestState.values["c"] == "conftest_test_c"
