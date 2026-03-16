"""Shared list across parallel tests — no locks needed for append.

With pytest-xdist this is impossible: each worker is a separate process,
so a plain Python list can't be shared without pickling, IPC, or a
database.

With pytest-threadpool, tests share the same process. Individual
list operations (append, extend, pop) are thread-safe in CPython:
- GIL builds: the GIL serializes bytecodes, making single operations atomic
- Free-threaded builds: PEP 703 added per-object locks to built-in types

The verify test runs in parallel alongside the writers.  A Barrier
synchronizes them: all 5 tests (4 writers + 1 verifier) must reach
the barrier before the verifier checks the final state.

SAFETY NOTE:
  Individual operations like list.append() are safe without locks.
  Compound operations (read-then-write, check-then-act, iteration while
  mutating) are NOT safe and require explicit synchronization:

    # UNSAFE — not atomic
    if item not in results:
        results.append(item)

    # UNSAFE — list may change mid-iteration
    for item in results:
        process(item)

    # SAFE — single atomic operation
    results.append(item)
"""

import threading
from time import sleep
from typing import ClassVar

import pytest


class TestSharedList:
    results: ClassVar[list] = []
    _barrier = threading.Barrier(5, timeout=10)

    @pytest.mark.parametrize("value", ["alpha", "beta", "gamma", "delta"])
    def test_append(self, value):
        """Each test appends to the same list from a different thread."""
        sleep(0.1)
        self.results.append(value)
        self._barrier.wait()

    def test_verify(self):
        """Wait for all writers, then check all 4 values are present."""
        self._barrier.wait()
        assert sorted(self.results) == ["alpha", "beta", "delta", "gamma"]
