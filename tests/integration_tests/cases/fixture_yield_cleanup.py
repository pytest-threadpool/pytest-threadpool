"""Yield fixture teardown runs after all parallel methods."""

from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestCleanup:
    flag: ClassVar[dict] = {"cleaned": False}

    @pytest.fixture(autouse=True, scope="class")
    def resource(self):
        self.flag["cleaned"] = False
        yield
        self.flag["cleaned"] = True

    def test_a(self):
        assert not self.flag["cleaned"]

    def test_b(self):
        assert not self.flag["cleaned"]


def test_verify():
    assert TestCleanup.flag["cleaned"]
