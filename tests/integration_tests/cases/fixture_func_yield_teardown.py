"""Function-scoped yield fixtures: setup and teardown both run per-test in parallel."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    setup_log: ClassVar[list] = []
    teardown_log: ClassVar[list] = []
    log_lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def resource(request):
    name = request.node.name
    with TestState.log_lock:
        TestState.setup_log.append(name)
    yield f"value_{name}"
    with TestState.log_lock:
        TestState.teardown_log.append(name)


@parallelizable("children")
class TestFuncYieldTeardown:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, resource):
        assert resource == "value_test_a"
        self.barrier.wait()

    def test_b(self, resource):
        assert resource == "value_test_b"
        self.barrier.wait()

    def test_c(self, resource):
        assert resource == "value_test_c"
        self.barrier.wait()


def test_verify():
    expected = {"test_a", "test_b", "test_c"}
    assert expected == set(TestState.setup_log), f"setups: {TestState.setup_log}"
    assert expected == set(TestState.teardown_log), f"teardowns: {TestState.teardown_log}"
    assert len(TestState.setup_log) == 3
    assert len(TestState.teardown_log) == 3
