"""Verify function-scoped fixture setup actually runs in parallel, not sequentially."""

import threading
import time
from typing import ClassVar

import pytest


class TestState:
    setup_starts: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def slow_resource(request):
    """Each setup takes 0.3s; record start time to prove overlap."""
    start = time.monotonic()
    with TestState.lock:
        TestState.setup_starts.append(start)
    time.sleep(0.3)
    return request.node.name


@pytest.mark.parallelizable("children")
class TestFixtureSetupParallel:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, slow_resource):
        self.barrier.wait()

    def test_b(self, slow_resource):
        self.barrier.wait()

    def test_c(self, slow_resource):
        self.barrier.wait()


def test_verify():
    # If setups ran in parallel, all 3 start times are close together.
    # If sequential, they'd be ~0.3s apart.
    # Check that the spread (max - min) is well below a single sleep duration.
    assert len(TestState.setup_starts) == 3
    spread = max(TestState.setup_starts) - min(TestState.setup_starts)
    assert spread < 0.2, (
        f"Fixture setup appears sequential: start time spread is {spread:.3f}s "
        f"(expected < 0.2s for parallel, ~0.6s for sequential)"
    )
