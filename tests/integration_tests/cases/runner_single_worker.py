"""Parallel-marked tests run correctly with --threadpool 1 (single worker fallback)."""

from typing import ClassVar

import pytest


class TestState:
    log: ClassVar[list] = []


@pytest.mark.parallelizable("children")
class TestSingleWorker:
    def test_a(self):
        TestState.log.append("a")

    def test_b(self):
        TestState.log.append("b")

    def test_c(self):
        TestState.log.append("c")


def test_verify():
    assert set(TestState.log) == {"a", "b", "c"}
