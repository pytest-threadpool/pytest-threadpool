"""xunit setup_method/teardown_method with mixed parallel and not_parallelizable methods."""

import threading
from typing import ClassVar

import pytest


class TestState:
    setup_log: ClassVar[list] = []
    teardown_log: ClassVar[list] = []
    threads: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.mark.parallelizable("children")
class TestMixedXunit:
    barrier = threading.Barrier(2, timeout=10)

    def setup_method(self, method):
        with TestState.lock:
            TestState.setup_log.append(method.__name__)
            TestState.threads[f"setup_{method.__name__}"] = threading.current_thread().name

    def teardown_method(self, method):
        with TestState.lock:
            TestState.teardown_log.append(method.__name__)
            TestState.threads[f"teardown_{method.__name__}"] = threading.current_thread().name

    def test_parallel_a(self):
        self.barrier.wait()

    def test_parallel_b(self):
        self.barrier.wait()

    @pytest.mark.not_parallelizable
    def test_sequential_c(self):
        pass


def test_verify():
    expected = {"test_parallel_a", "test_parallel_b", "test_sequential_c"}
    assert expected == set(TestState.setup_log), f"setup_method missing: {TestState.setup_log}"
    assert expected == set(TestState.teardown_log), (
        f"teardown_method missing: {TestState.teardown_log}"
    )
    # Sequential method runs on MainThread
    assert TestState.threads["setup_test_sequential_c"] == "MainThread"
    assert TestState.threads["teardown_test_sequential_c"] == "MainThread"
