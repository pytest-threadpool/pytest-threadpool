"""xunit setup_function/teardown_function with mixed parallel and sequential bare functions."""

import threading
from typing import ClassVar

from pytest_threadpool import not_parallelizable, parallelizable


class TestState:
    setup_log: ClassVar[list] = []
    teardown_log: ClassVar[list] = []
    threads: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


pytestmark = parallelizable("children")


def setup_function(function):
    with TestState.lock:
        TestState.setup_log.append(function.__name__)
        TestState.threads[f"setup_{function.__name__}"] = threading.current_thread().name


def teardown_function(function):
    with TestState.lock:
        TestState.teardown_log.append(function.__name__)
        TestState.threads[f"teardown_{function.__name__}"] = threading.current_thread().name


barrier = threading.Barrier(2, timeout=10)


def test_parallel_a():
    barrier.wait()


def test_parallel_b():
    barrier.wait()


@not_parallelizable
def test_sequential_c():
    pass


@not_parallelizable
def test_verify():
    # test_verify itself also triggers setup_function/teardown_function
    expected = {"test_parallel_a", "test_parallel_b", "test_sequential_c"}
    assert expected.issubset(set(TestState.setup_log)), (
        f"setup_function missing: {TestState.setup_log}"
    )
    # teardown for test_verify hasn't run yet, so only check the first three
    assert expected.issubset(set(TestState.teardown_log)), (
        f"teardown_function missing: {TestState.teardown_log}"
    )
    # Sequential function runs on MainThread
    assert TestState.threads["setup_test_sequential_c"] == "MainThread"
    assert TestState.threads["teardown_test_sequential_c"] == "MainThread"
