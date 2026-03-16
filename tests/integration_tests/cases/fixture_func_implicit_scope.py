"""Fixtures without explicit scope are function-scoped and must be cloned per-item."""

import threading
from typing import ClassVar

import pytest


class TestState:
    values: ClassVar[dict] = {}
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def no_scope_fixture(request):
    """Fixture with no explicit scope — defaults to function."""
    return f"value_{request.node.name}"


@pytest.fixture
def empty_parens_fixture(request):
    """Fixture with empty parens — also defaults to function."""
    return f"ep_{request.node.name}"


@pytest.mark.parallelizable("children")
class TestImplicitFunctionScope:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, no_scope_fixture, empty_parens_fixture):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["a_no"] = no_scope_fixture
            TestState.values["a_ep"] = empty_parens_fixture

    def test_b(self, no_scope_fixture, empty_parens_fixture):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["b_no"] = no_scope_fixture
            TestState.values["b_ep"] = empty_parens_fixture

    def test_c(self, no_scope_fixture, empty_parens_fixture):
        self.barrier.wait()
        with TestState.lock:
            TestState.values["c_no"] = no_scope_fixture
            TestState.values["c_ep"] = empty_parens_fixture


def test_verify():
    # Each test got its own fixture instance (unique per test name)
    assert TestState.values["a_no"] == "value_test_a"
    assert TestState.values["b_no"] == "value_test_b"
    assert TestState.values["c_no"] == "value_test_c"
    assert TestState.values["a_ep"] == "ep_test_a"
    assert TestState.values["b_ep"] == "ep_test_b"
    assert TestState.values["c_ep"] == "ep_test_c"
