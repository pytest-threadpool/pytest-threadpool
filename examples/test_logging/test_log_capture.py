"""Shared log collector — thread-safe alternative to caplog.

pytest's ``caplog`` fixture is NOT thread-safe: log records from parallel
tests leak across fixtures, and ``at_level()`` context managers race with
each other on the shared root logger.

This pattern uses a shared thread-safe list to collect structured records
across parallel tests — impossible with pytest-xdist since workers are
separate processes.
"""

import threading
from typing import ClassVar

import pytest


class TestSharedLogCollector:
    """Collect structured log data in a thread-safe list."""

    _records: ClassVar[list] = []
    _lock = threading.Lock()

    @pytest.mark.parametrize("_worker", range(4))
    def test_collect_structured_records(self, _worker):
        """Each test appends its own record — Lock prevents data races."""
        record = {"worker": _worker, "thread": threading.current_thread().name}

        with self._lock:
            self._records.append(record)

        with self._lock:
            my_records = [r for r in self._records if r["worker"] == _worker]
        assert len(my_records) == 1
