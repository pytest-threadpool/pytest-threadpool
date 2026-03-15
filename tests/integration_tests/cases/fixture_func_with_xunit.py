"""Function-scoped fixtures combined with xunit setup_method/teardown_method."""

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
class TestFixtureWithXunit:
    barrier = threading.Barrier(3, timeout=10)

    def setup_method(self, method):
        with TestState.lock:
            TestState.log.append(f"xunit_setup_{method.__name__}")

    def teardown_method(self, method):
        with TestState.lock:
            TestState.log.append(f"xunit_teardown_{method.__name__}")

    def test_a(self, fx_resource):
        assert fx_resource == "fx_test_a"
        self.barrier.wait()

    def test_b(self, fx_resource):
        assert fx_resource == "fx_test_b"
        self.barrier.wait()

    def test_c(self, fx_resource):
        assert fx_resource == "fx_test_c"
        self.barrier.wait()


def test_verify():
    tests = ("test_a", "test_b", "test_c")
    for name in tests:
        assert f"fixture_setup_{name}" in TestState.log, f"missing fixture setup for {name}"
        assert f"fixture_teardown_{name}" in TestState.log, f"missing fixture teardown for {name}"
        assert f"xunit_setup_{name}" in TestState.log, f"missing xunit setup for {name}"
        assert f"xunit_teardown_{name}" in TestState.log, f"missing xunit teardown for {name}"
