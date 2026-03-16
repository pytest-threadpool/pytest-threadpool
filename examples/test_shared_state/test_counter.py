"""Thread-safe counter shared across parallel tests.

This pattern is impossible with pytest-xdist — each worker is a separate
process, so a plain Python object with a Lock can't be shared without
external coordination (Redis, a database, file locks).

With pytest-threadpool, all tests share the same process.  A Lock
protects the compound read-then-write operation that ``+=`` compiles to.

SAFETY NOTE:
  ``counter += 1`` is NOT atomic — it compiles to LOAD, ADD, STORE.
  Two threads can read the same value, both add 1, and both store the
  same result, losing an increment.  Always use a Lock for compound
  operations:

    # UNSAFE — race condition
    counter += 1

    # SAFE — Lock serializes the read-modify-write
    with lock:
        counter += 1
"""

import threading
from typing import ClassVar

import pytest


class TestCounter:
    """Each test atomically increments a shared counter and verifies its own increment."""

    _lock = threading.Lock()
    _counter: ClassVar[int] = 0

    @pytest.mark.parametrize("_worker", range(10))
    def test_increment(self, _worker):
        """Atomically increment and verify the counter moved forward."""
        with self._lock:
            before = TestCounter._counter
            TestCounter._counter += 1
            after = TestCounter._counter
        assert after == before + 1
