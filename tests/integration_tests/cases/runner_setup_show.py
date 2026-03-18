"""Parallel group with --setup-show displays fixture setup/teardown."""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture
def resource():
    return "value"


@parallelizable("children")
class TestSetupShow:
    def test_a(self, resource):
        assert resource == "value"

    def test_b(self, resource):
        assert resource == "value"
