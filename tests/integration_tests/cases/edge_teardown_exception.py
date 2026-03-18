"""Teardown raises an exception in a parallel group."""

from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    results: ClassVar[list] = []


@pytest.fixture
def exploding_teardown(request):
    yield "ok"
    if request.node.name == "test_a":
        raise RuntimeError("teardown explodes")


@parallelizable("children")
class TestTeardownFails:
    def test_a(self, exploding_teardown):
        TestState.results.append("a")

    def test_b(self, exploding_teardown):
        TestState.results.append("b")

    def test_c(self, exploding_teardown):
        TestState.results.append("c")


def test_verify():
    assert sorted(TestState.results) == ["a", "b", "c"]
