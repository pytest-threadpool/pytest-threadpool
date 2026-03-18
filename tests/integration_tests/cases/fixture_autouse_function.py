"""Autouse function-scoped fixtures work correctly in parallel groups."""

import threading

import pytest

from pytest_threadpool import parallelizable

setup_log = []
teardown_log = []
log_lock = threading.Lock()


@pytest.fixture(autouse=True)
def auto_resource(request):
    with log_lock:
        setup_log.append(request.node.name)
    yield request.node.name
    with log_lock:
        teardown_log.append(request.node.name)


@parallelizable("children")
class TestAutouseFunction:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, auto_resource):
        self.barrier.wait()
        assert auto_resource == "test_a"

    def test_b(self, auto_resource):
        self.barrier.wait()
        assert auto_resource == "test_b"

    def test_c(self, auto_resource):
        self.barrier.wait()
        assert auto_resource == "test_c"


def test_verify_setup_teardown():
    class_tests = {"test_a", "test_b", "test_c"}
    assert class_tests.issubset(setup_log)
    assert class_tests.issubset(teardown_log)
