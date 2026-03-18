"""Class-scoped fixture runs exactly once despite parallel methods."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestOnce:
    setup_count: ClassVar[list] = []
    barrier = threading.Barrier(3, timeout=10)

    @pytest.fixture(autouse=True, scope="class")
    def db(self):
        self.setup_count.append(1)
        return

    def test_a(self):
        self.barrier.wait()
        assert len(self.setup_count) == 1

    def test_b(self):
        self.barrier.wait()
        assert len(self.setup_count) == 1

    def test_c(self):
        self.barrier.wait()
        assert len(self.setup_count) == 1
