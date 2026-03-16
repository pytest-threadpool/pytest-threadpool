"""Parallel group with --setup-show displays fixture setup/teardown."""

import pytest


@pytest.fixture
def resource():
    return "value"


@pytest.mark.parallelizable("children")
class TestSetupShow:
    def test_a(self, resource):
        assert resource == "value"

    def test_b(self, resource):
        assert resource == "value"
