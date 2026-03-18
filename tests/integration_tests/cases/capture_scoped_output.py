"""Fixtures at every scope level printing identifiable output.

Used to verify that captured output is associated with the correct
scope in test reports (setup sections, call output, teardown sections).
"""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture(autouse=True, scope="session")
def fx_session():
    print("SESSION_SETUP")
    yield
    print("SESSION_TEARDOWN")


@pytest.fixture(autouse=True, scope="package")
def fx_package():
    print("PACKAGE_SETUP")
    yield
    print("PACKAGE_TEARDOWN")


@pytest.fixture(autouse=True, scope="module")
def fx_module():
    print("MODULE_SETUP")
    yield
    print("MODULE_TEARDOWN")


@pytest.fixture(autouse=True, scope="class")
def fx_class():
    print("CLASS_SETUP")
    yield
    print("CLASS_TEARDOWN")


@pytest.fixture(autouse=True)
def fx_function():
    print("FUNCTION_SETUP")
    yield
    print("FUNCTION_TEARDOWN")


@parallelizable("children")
class TestScopedOutput:
    def test_alpha(self):
        print("CALL_ALPHA")

    def test_beta(self):
        print("CALL_BETA")

    @pytest.mark.parametrize("n", range(3))
    def test_param(self, n):
        print(f"CALL_PARAM_{n}")
