"""Function-scoped fixtures with mixed parallel and not_parallelizable methods."""

import threading
from typing import ClassVar

import pytest


class TestState:
    log: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def fx_resource(request):
    name = request.node.name
    with TestState.lock:
        TestState.log.append(f"fixture_setup_{name}")
    yield f"fx_{name}"
    with TestState.lock:
        TestState.log.append(f"fixture_teardown_{name}")


@pytest.mark.parallelizable("children")
class TestMixedFixtures:
    barrier = threading.Barrier(2, timeout=10)

    def test_parallel_a(self, fx_resource):
        assert fx_resource == "fx_test_parallel_a"
        self.barrier.wait()

    def test_parallel_b(self, fx_resource):
        assert fx_resource == "fx_test_parallel_b"
        self.barrier.wait()

    @pytest.mark.not_parallelizable
    def test_sequential_c(self, fx_resource):
        assert fx_resource == "fx_test_sequential_c"


def test_verify():
    tests = ("test_parallel_a", "test_parallel_b", "test_sequential_c")
    for name in tests:
        assert f"fixture_setup_{name}" in TestState.log, f"missing fixture setup for {name}"
        assert f"fixture_teardown_{name}" in TestState.log, f"missing fixture teardown for {name}"
