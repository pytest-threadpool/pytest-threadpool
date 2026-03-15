"""Function-scoped fixture depending on another function-scoped fixture."""

import threading
from typing import ClassVar

import pytest


class TestState:
    teardown_order: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def base_resource(request):
    name = request.node.name
    yield f"base({name})"
    with TestState.lock:
        TestState.teardown_order.append(f"base_teardown_{name}")


@pytest.fixture
def derived_resource(base_resource, request):
    name = request.node.name
    yield f"derived({base_resource})"
    with TestState.lock:
        TestState.teardown_order.append(f"derived_teardown_{name}")


@pytest.mark.parallelizable("children")
class TestFuncChain:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, derived_resource):
        assert derived_resource == "derived(base(test_a))"
        self.barrier.wait()

    def test_b(self, derived_resource):
        assert derived_resource == "derived(base(test_b))"
        self.barrier.wait()

    def test_c(self, derived_resource):
        assert derived_resource == "derived(base(test_c))"
        self.barrier.wait()


def test_verify():
    # Each test should have both teardowns in LIFO order (derived before base)
    for test_name in ("test_a", "test_b", "test_c"):
        derived_idx = TestState.teardown_order.index(f"derived_teardown_{test_name}")
        base_idx = TestState.teardown_order.index(f"base_teardown_{test_name}")
        assert derived_idx < base_idx, (
            f"derived must tear down before base for {test_name}: {TestState.teardown_order}"
        )
