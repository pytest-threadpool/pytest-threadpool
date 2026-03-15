"""All tests in a parallel group fail during setup."""

import pytest


@pytest.fixture
def broken():
    raise RuntimeError("setup explodes")


@pytest.mark.parallelizable("children")
class TestAllSetupFail:
    def test_a(self, broken):
        pass

    def test_b(self, broken):
        pass

    def test_c(self, broken):
        pass
