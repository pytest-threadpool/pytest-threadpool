"""Verify teardown runs in the same worker thread as the test call."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    call_threads: ClassVar[dict] = {}
    teardown_threads: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def tracked_resource(request):
    name = request.node.name
    yield name
    with TestState.lock:
        TestState.teardown_threads[name] = threading.current_thread().name


@parallelizable("children")
class TestTeardownSameThread:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, tracked_resource):
        with TestState.lock:
            TestState.call_threads["test_a"] = threading.current_thread().name
        self.barrier.wait()

    def test_b(self, tracked_resource):
        with TestState.lock:
            TestState.call_threads["test_b"] = threading.current_thread().name
        self.barrier.wait()

    def test_c(self, tracked_resource):
        with TestState.lock:
            TestState.call_threads["test_c"] = threading.current_thread().name
        self.barrier.wait()


def test_verify():
    for name in ("test_a", "test_b", "test_c"):
        assert name in TestState.call_threads, f"missing call thread for {name}"
        assert name in TestState.teardown_threads, f"missing teardown thread for {name}"
        assert TestState.call_threads[name] == TestState.teardown_threads[name], (
            f"{name}: call ran on {TestState.call_threads[name]} "
            f"but teardown ran on {TestState.teardown_threads[name]}"
        )
