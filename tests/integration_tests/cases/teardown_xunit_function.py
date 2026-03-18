"""xunit teardown_function runs in worker threads for parallel bare functions."""

import threading
from typing import ClassVar

from pytest_threadpool import not_parallelizable, parallelizable

pytestmark = parallelizable("children")


class TestState:
    setup_threads: ClassVar[dict] = {}
    teardown_threads: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


def setup_function(function):
    with TestState.lock:
        TestState.setup_threads[function.__name__] = threading.current_thread().name


def teardown_function(function):
    with TestState.lock:
        TestState.teardown_threads[function.__name__] = threading.current_thread().name


barrier = threading.Barrier(3, timeout=10)


def test_alpha():
    barrier.wait()


def test_beta():
    barrier.wait()


def test_gamma():
    barrier.wait()


@not_parallelizable
def test_verify():
    for name in ("test_alpha", "test_beta", "test_gamma"):
        assert name in TestState.setup_threads, f"missing setup for {name}"
        assert name in TestState.teardown_threads, f"missing teardown for {name}"
        # setup and teardown should run on the same worker thread
        assert TestState.setup_threads[name] == TestState.teardown_threads[name], (
            f"{name}: setup on {TestState.setup_threads[name]} "
            f"but teardown on {TestState.teardown_threads[name]}"
        )
