"""Barrier synchronization across parallel tests.

This pattern is impossible with pytest-xdist — processes can't share
a threading.Barrier.

With pytest-threadpool, a Barrier lets tests synchronize at a
checkpoint: all N tests must reach the barrier before any can proceed.
This is useful for testing behaviour under true concurrent load — e.g.
verifying a rate limiter, testing for deadlocks, or ensuring a service
handles simultaneous requests.

Each test is independent: it does work, waits at the barrier, then
verifies its own postcondition.
"""

import threading
from time import monotonic, sleep
from typing import ClassVar

import pytest

N_WORKERS = 4


class TestBarrierSync:
    """All workers synchronize at a checkpoint, then each verifies timing."""

    _barrier = threading.Barrier(N_WORKERS, timeout=10)
    _arrival_times: ClassVar[list] = []

    @pytest.mark.parametrize("_worker", range(N_WORKERS))
    def test_synchronized_start(self, _worker):
        """Staggered setup, synchronized checkpoint, then verify all arrived together."""
        # Staggered work before the checkpoint
        sleep(_worker * 0.02)

        # Everyone waits here — no test proceeds until all N arrive
        self._barrier.wait()
        self._arrival_times.append(monotonic())

        # Each test independently verifies the post-barrier state:
        # at least N timestamps exist and they're all within a tight window
        while len(self._arrival_times) < N_WORKERS:
            sleep(0.001)

        spread = max(self._arrival_times) - min(self._arrival_times)
        assert spread < 0.1, f"Arrivals spread {spread:.3f}s — barrier didn't synchronize"
