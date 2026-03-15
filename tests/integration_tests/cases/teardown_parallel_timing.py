"""Verify function-scoped fixture teardown runs in parallel, not sequentially."""

import threading
import time
from typing import ClassVar

import pytest


class TestState:
    start_time: ClassVar[float] = time.monotonic()
    teardown_end_times: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def slow_teardown_resource():
    yield "value"
    # Each teardown takes 0.2s; if sequential that's 0.6s total
    time.sleep(0.2)
    with TestState.lock:
        TestState.teardown_end_times.append(time.monotonic())


@pytest.mark.parallelizable("children")
class TestParallelTeardown:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, slow_teardown_resource):
        self.barrier.wait()

    def test_b(self, slow_teardown_resource):
        self.barrier.wait()

    def test_c(self, slow_teardown_resource):
        self.barrier.wait()


def test_verify():
    assert len(TestState.teardown_end_times) == 3
    elapsed = max(TestState.teardown_end_times) - TestState.start_time
    # 3 x 0.2s sequential = 0.6s; parallel should be well under that
    assert elapsed < 0.5, (
        f"Teardown appears sequential: {elapsed:.2f}s elapsed "
        f"(3 x 0.2s = 0.6s sequential, expected < 0.5s parallel)"
    )
