"""Teardown runs even when the test call fails."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    teardown_log: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def resource_with_cleanup(request):
    name = request.node.name
    yield name
    with TestState.lock:
        TestState.teardown_log.append(name)


@parallelizable("children")
class TestTeardownAfterFailure:
    def test_pass(self, resource_with_cleanup):
        assert True

    def test_fail(self, resource_with_cleanup):
        pytest.fail("intentional failure")

    def test_raise(self, resource_with_cleanup):
        raise RuntimeError("intentional")


def test_verify():
    expected = {"test_pass", "test_fail", "test_raise"}
    assert expected == set(TestState.teardown_log), (
        f"teardown must run for all tests including failures: {TestState.teardown_log}"
    )
