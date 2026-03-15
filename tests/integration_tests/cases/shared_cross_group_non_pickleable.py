"""Non-pickleable thread-safe objects shared across different parallel groups."""

import threading
from typing import ClassVar

import pytest


class SharedState:
    lock = threading.Lock()
    event = threading.Event()
    results: ClassVar[dict] = {}


@pytest.mark.parallelizable("children")
class TestGroupA:
    barrier = threading.Barrier(2, timeout=10)

    def test_a1(self):
        self.barrier.wait()
        with SharedState.lock:
            SharedState.results["a1"] = True

    def test_a2(self):
        self.barrier.wait()
        with SharedState.lock:
            SharedState.results["a2"] = True


@pytest.mark.parallelizable("children")
class TestGroupB:
    barrier = threading.Barrier(2, timeout=10)

    def test_b1(self):
        self.barrier.wait()
        with SharedState.lock:
            SharedState.results["b1"] = True
        SharedState.event.set()

    def test_b2(self):
        self.barrier.wait()
        assert SharedState.event.wait(timeout=10)
        with SharedState.lock:
            SharedState.results["b2"] = True


def test_verify():
    assert SharedState.results == {"a1": True, "a2": True, "b1": True, "b2": True}
