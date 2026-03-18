"""Verify setup_method AND teardown_method both run for every parallel test."""

import threading
from typing import ClassVar

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestMethodTeardown:
    setup_log: ClassVar[list] = []
    teardown_log: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()
    barrier = threading.Barrier(3, timeout=10)

    def setup_method(self, method):
        with self.lock:
            self.setup_log.append(method.__name__)

    def teardown_method(self, method):
        with self.lock:
            self.teardown_log.append(method.__name__)

    def test_a(self):
        self.barrier.wait()

    def test_b(self):
        self.barrier.wait()

    def test_c(self):
        self.barrier.wait()


def test_verify():
    expected = {"test_a", "test_b", "test_c"}
    assert expected == set(TestMethodTeardown.setup_log), (
        f"setup_method missing: {TestMethodTeardown.setup_log}"
    )
    assert expected == set(TestMethodTeardown.teardown_log), (
        f"teardown_method missing: {TestMethodTeardown.teardown_log}"
    )
    assert len(TestMethodTeardown.setup_log) == 3
    assert len(TestMethodTeardown.teardown_log) == 3
