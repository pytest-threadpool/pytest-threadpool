"""Concurrent dict writes from parallel methods are consistent."""
import pytest


@pytest.mark.parallelizable("children")
class TestDict:
    shared = {}

    def _write(self, key, base, n=1000):
        for i in range(n):
            self.shared[f"{key}_{i}"] = base + i

    def test_a(self):
        self._write("a", 0)

    def test_b(self):
        self._write("b", 10_000)

    def test_c(self):
        self._write("c", 20_000)


def test_verify():
    d = TestDict.shared
    for prefix, base in [("a", 0), ("b", 10_000), ("c", 20_000)]:
        for i in range(1000):
            assert f"{prefix}_{i}" in d
            assert d[f"{prefix}_{i}"] == base + i
