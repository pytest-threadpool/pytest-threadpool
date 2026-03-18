"""Verify function-scoped fixture teardown runs in parallel, not sequentially."""

import threading
import time
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    teardown_end_times: ClassVar[list] = []
    call_end_times: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def slow_teardown_resource():
    yield "value"
    # Each teardown takes 0.2s; if sequential that's 0.6s total
    time.sleep(0.2)
    with TestState.lock:
        TestState.teardown_end_times.append(time.monotonic())


@parallelizable("children")
class TestParallelTeardown:
    barrier = threading.Barrier(3, timeout=10)

    def _record_call(self):
        with TestState.lock:
            TestState.call_end_times.append(time.monotonic())

    def test_a(self, slow_teardown_resource):
        self.barrier.wait()
        self._record_call()

    def test_b(self, slow_teardown_resource):
        self.barrier.wait()
        self._record_call()

    def test_c(self, slow_teardown_resource):
        self.barrier.wait()
        self._record_call()


def test_verify():
    assert len(TestState.teardown_end_times) == 3
    assert len(TestState.call_end_times) == 3
    # Measure from when tests finished to when all teardowns completed
    teardown_duration = max(TestState.teardown_end_times) - max(TestState.call_end_times)
    # 3 x 0.2s sequential = 0.6s; parallel should complete in ~0.2s + overhead
    assert teardown_duration < 0.45, (
        f"Teardown appears sequential: {teardown_duration:.2f}s "
        f"(3 x 0.2s = 0.6s sequential, expected < 0.45s parallel)"
    )
