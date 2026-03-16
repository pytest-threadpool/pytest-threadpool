"""logging in parallel tests — caplog pitfalls and working alternatives.

pytest's ``caplog`` fixture is NOT thread-safe: log records from parallel
tests leak across fixtures, and ``at_level()`` context managers race with
each other on the shared root logger.

**What works instead:**

- Use Python's ``logging`` module with a per-test ``FileHandler`` writing
  to ``tmp_path`` — each test gets its own directory and log file.
- Use a shared thread-safe list to collect structured records (see below).
- Use a ``ContextLocal`` provider from a DI container to scope log
  collectors per test — see ``examples/test_di/container.py`` for an
  example of ``ContextLocal`` that resets automatically between tests.
"""

import logging
import threading
from typing import ClassVar

import pytest


class TestLogToFile:
    """Each test creates its own logger + file handler in tmp_path."""

    @pytest.mark.parametrize("_worker", range(4))
    def test_per_test_file_log(self, _worker, tmp_path):
        """Write logs to a per-test file — no interleaving, fully isolated."""
        log_file = tmp_path / "test.log"

        log = logging.getLogger(f"worker.{_worker}.{id(self)}")
        log.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        log.addHandler(handler)

        try:
            log.debug("step 1")
            log.info("step 2")
            log.warning("step 3")
        finally:
            handler.close()
            log.removeHandler(handler)

        lines = log_file.read_text().splitlines()
        assert lines == ["DEBUG: step 1", "INFO: step 2", "WARNING: step 3"]


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
