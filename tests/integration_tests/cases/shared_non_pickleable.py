"""Non-pickleable thread-safe objects shared across parallel children."""

import logging
import threading
from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestNonPickleable:
    lock = threading.Lock()
    condition = threading.Condition()
    semaphore = threading.Semaphore(3)
    logger = logging.getLogger("test_non_pickleable")
    results: ClassVar[dict] = {}

    def test_lock(self):
        with self.lock:
            self.results["lock"] = threading.current_thread().name

    def test_condition(self):
        with self.condition:
            self.results["condition"] = threading.current_thread().name
            self.condition.notify_all()

    def test_semaphore(self):
        with self.semaphore:
            self.results["semaphore"] = threading.current_thread().name

    def test_logger(self):
        self.logger.info("parallel log from %s", threading.current_thread().name)
        self.results["logger"] = threading.current_thread().name


def test_verify():
    assert set(TestNonPickleable.results) == {"lock", "condition", "semaphore", "logger"}
