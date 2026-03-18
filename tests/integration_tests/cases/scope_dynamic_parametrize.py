"""Dynamic parametrize via pytest_generate_tests with parallel markers."""

import threading

from pytest_threadpool import parallelizable

pytestmark = parallelizable("parameters")

barrier = threading.Barrier(3, timeout=10)


def pytest_generate_tests(metafunc):
    if "dynamic_val" in metafunc.fixturenames:
        metafunc.parametrize("dynamic_val", [10, 20, 30])


def test_dynamic(dynamic_val):
    barrier.wait()
    assert dynamic_val in (10, 20, 30)
