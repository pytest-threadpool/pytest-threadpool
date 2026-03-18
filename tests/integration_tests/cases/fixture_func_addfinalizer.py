"""Function-scoped fixture using request.addfinalizer (non-yield style)."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    setup_log: ClassVar[list] = []
    finalizer_log: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def managed_resource(request):
    name = request.node.name
    with TestState.lock:
        TestState.setup_log.append(name)

    def cleanup():
        with TestState.lock:
            TestState.finalizer_log.append(name)

    request.addfinalizer(cleanup)  # noqa: PT021 — intentionally testing addfinalizer API
    return f"resource_{name}"


@parallelizable("children")
class TestAddfinalizer:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, managed_resource):
        assert managed_resource == "resource_test_a"
        self.barrier.wait()

    def test_b(self, managed_resource):
        assert managed_resource == "resource_test_b"
        self.barrier.wait()

    def test_c(self, managed_resource):
        assert managed_resource == "resource_test_c"
        self.barrier.wait()


def test_verify():
    expected = {"test_a", "test_b", "test_c"}
    assert expected == set(TestState.setup_log), f"setups: {TestState.setup_log}"
    assert expected == set(TestState.finalizer_log), f"finalizers: {TestState.finalizer_log}"
