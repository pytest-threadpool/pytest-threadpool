"""Verify function-scoped fixture setup actually runs in parallel, not sequentially."""

import threading
import time
from typing import ClassVar

import pytest


@pytest.fixture
def slow_resource(request):
    """Each setup takes 0.2s; if sequential that's 0.6s total, parallel < 0.4s."""
    time.sleep(0.2)
    return request.node.name


@pytest.mark.parallelizable("children")
class TestFixtureSetupParallel:
    barrier = threading.Barrier(3, timeout=10)
    start_time: ClassVar[float | None] = None
    end_times: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()

    def test_a(self, slow_resource):
        self.barrier.wait()
        with self.lock:
            self.end_times.append(time.monotonic())

    def test_b(self, slow_resource):
        self.barrier.wait()
        with self.lock:
            self.end_times.append(time.monotonic())

    def test_c(self, slow_resource):
        self.barrier.wait()
        with self.lock:
            self.end_times.append(time.monotonic())


TestFixtureSetupParallel.start_time = time.monotonic()


def test_verify():
    # All 3 tests completed — the barrier proves concurrency of the test calls.
    # The fixture setup (0.2s each) ran in parallel, so total wall time
    # should be well under 0.6s (the sequential total).
    elapsed = max(TestFixtureSetupParallel.end_times) - TestFixtureSetupParallel.start_time
    assert elapsed < 0.5, (
        f"Fixture setup appears sequential: {elapsed:.2f}s elapsed "
        f"(3 x 0.2s = 0.6s sequential, expected < 0.5s parallel)"
    )
