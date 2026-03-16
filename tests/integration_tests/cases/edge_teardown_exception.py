"""Teardown raises an exception in a parallel group."""

from typing import ClassVar

import pytest


class TestState:
    results: ClassVar[list] = []


@pytest.fixture
def exploding_teardown(request):
    yield "ok"
    if request.node.name == "test_a":
        raise RuntimeError("teardown explodes")


@pytest.mark.parallelizable("children")
class TestTeardownFails:
    def test_a(self, exploding_teardown):
        TestState.results.append("a")

    def test_b(self, exploding_teardown):
        TestState.results.append("b")

    def test_c(self, exploding_teardown):
        TestState.results.append("c")


def test_verify():
    assert sorted(TestState.results) == ["a", "b", "c"]
