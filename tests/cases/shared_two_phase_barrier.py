"""Two-phase barrier proves tests truly run concurrently."""

import threading
from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestBarrier:
    barrier = threading.Barrier(3, timeout=10)
    verify_barrier = threading.Barrier(3, timeout=10)
    arrived: ClassVar[dict] = {}

    def _arrive(self, name):
        self.barrier.wait()
        self.arrived[name] = True
        self.verify_barrier.wait()
        assert self.arrived == {"a": True, "b": True, "c": True}

    def test_a(self):
        self._arrive("a")

    def test_b(self):
        self._arrive("b")

    def test_c(self):
        self._arrive("c")
