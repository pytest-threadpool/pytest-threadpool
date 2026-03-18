"""All tests in a parallel group fail during setup."""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture
def broken():
    raise RuntimeError("setup explodes")


@parallelizable("children")
class TestAllSetupFail:
    def test_a(self, broken):
        pass

    def test_b(self, broken):
        pass

    def test_c(self, broken):
        pass
