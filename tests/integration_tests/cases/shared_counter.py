"""Each thread counts independently, results are correct."""

from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestCounter:
    results: ClassVar[dict] = {}

    def _count(self, name, n=50_000):
        total = 0
        for _ in range(n):
            total += 1
        self.results[name] = total

    def test_a(self):
        self._count("a")

    def test_b(self):
        self._count("b")

    def test_c(self):
        self._count("c")


def test_verify():
    for name in ("a", "b", "c"):
        assert TestCounter.results[name] == 50_000
