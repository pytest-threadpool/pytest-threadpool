"""First item in parallel group fails setup — remaining items still run."""

from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    results: ClassVar[list] = []


@pytest.fixture
def first_breaks(request):
    if request.node.name == "test_a":
        raise RuntimeError("first item setup explodes")
    return "ok"


@parallelizable("children")
class TestFirstSetupFails:
    def test_a(self, first_breaks):
        pass

    def test_b(self, first_breaks):
        TestState.results.append("b")

    def test_c(self, first_breaks):
        TestState.results.append("c")


def test_verify():
    assert sorted(TestState.results) == ["b", "c"]
