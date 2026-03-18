"""Parallel-marked tests work with --setup-only."""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture
def fx_resource(tmp_path):
    return tmp_path / "resource"


@parallelizable("children")
class TestSetupOnly:
    def test_a(self, fx_resource):
        pass

    def test_b(self, fx_resource):
        pass

    def test_c(self):
        pass
