"""xunit teardown_method runs in the same worker thread as setup_method and test."""

import threading
from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestMethodTeardownThread:
    setup_threads: ClassVar[dict] = {}
    call_threads: ClassVar[dict] = {}
    teardown_threads: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()
    barrier = threading.Barrier(3, timeout=10)

    def setup_method(self, method):
        with self.lock:
            self.setup_threads[method.__name__] = threading.current_thread().name

    def teardown_method(self, method):
        with self.lock:
            self.teardown_threads[method.__name__] = threading.current_thread().name

    def test_a(self):
        with self.lock:
            self.call_threads["test_a"] = threading.current_thread().name
        self.barrier.wait()

    def test_b(self):
        with self.lock:
            self.call_threads["test_b"] = threading.current_thread().name
        self.barrier.wait()

    def test_c(self):
        with self.lock:
            self.call_threads["test_c"] = threading.current_thread().name
        self.barrier.wait()


def test_verify():
    for name in ("test_a", "test_b", "test_c"):
        setup_t = TestMethodTeardownThread.setup_threads[name]
        call_t = TestMethodTeardownThread.call_threads[name]
        teardown_t = TestMethodTeardownThread.teardown_threads[name]
        assert setup_t == call_t == teardown_t, (
            f"{name}: setup={setup_t}, call={call_t}, teardown={teardown_t} — "
            f"all three must run on the same worker thread"
        )
