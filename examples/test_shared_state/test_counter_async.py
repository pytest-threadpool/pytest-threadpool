"""Async version of the thread-safe counter example.

Each test runs its own asyncio event loop via ``asyncio.run()``.
The counter and Lock are shared across threads — ``threading.Lock``
works correctly here since each ``asyncio.run()`` blocks its thread
while the coroutine runs.
"""

import asyncio
import functools
import threading
from typing import ClassVar

import pytest


def async_test(fn):
    """Run an async test function in its own event loop."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class TestCounterAsync:
    """Each test atomically increments a shared counter and verifies its own increment."""

    _lock = threading.Lock()
    _counter: ClassVar[int] = 0

    @async_test
    @pytest.mark.parametrize("_worker", range(10))
    async def test_increment(self, _worker):
        """Atomically increment and verify the counter moved forward."""
        await asyncio.sleep(0.01)  # simulate async I/O
        with self._lock:
            before = TestCounterAsync._counter
            TestCounterAsync._counter += 1
            after = TestCounterAsync._counter
        assert after == before + 1
