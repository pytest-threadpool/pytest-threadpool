"""Shared dict across parallel tests — no locks needed for single key writes.

With pytest-xdist this is impossible: each worker is a separate process,
so a plain Python dict can't be shared without external storage.

With pytest-threadpool, tests share the same process. Individual dict
operations (d[key] = value, d.get(), d.pop()) are thread-safe in CPython:
- GIL builds: the GIL serializes bytecodes, making single operations atomic
- Free-threaded builds: PEP 703 added per-object locks to built-in types

The verify test runs in parallel alongside the writers.  A Barrier
synchronizes them: all 5 tests (4 writers + 1 verifier) must reach
the barrier before the verifier checks the final state.

SAFETY NOTE:
  Individual operations like d[key] = value are safe without locks.
  Compound operations are NOT safe and require explicit synchronization:

    # UNSAFE — read-then-write is not atomic
    d[key] = d.get(key, 0) + 1

    # UNSAFE — dict may change mid-iteration
    for key in d:
        process(d[key])

    # SAFE — single atomic write
    d[key] = value

  For counters, use threading.Lock or collections from the threading module.
"""

import threading
from time import sleep
from typing import ClassVar

import pytest


class TestSharedDict:
    results: ClassVar[dict] = {}
    _barrier = threading.Barrier(5, timeout=10)

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("host", "localhost"),
            ("port", 8080),
            ("env", "test"),
            ("debug", True),
        ],
    )
    def test_write(self, key, value):
        """Each test writes a different key to the same dict from a different thread."""
        sleep(0.1)
        self.results[key] = value
        self._barrier.wait()

    def test_verify(self):
        """Wait for all writers, then check all 4 entries are present."""
        self._barrier.wait()
        assert self.results == {
            "host": "localhost",
            "port": 8080,
            "env": "test",
            "debug": True,
        }
