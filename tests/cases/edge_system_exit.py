"""Test body raises SystemExit during parallel execution."""

import pytest


@pytest.mark.parallelizable("children")
class TestSystemExit:
    def test_normal(self):
        assert True

    def test_exits(self):
        raise SystemExit(42)

    def test_also_normal(self):
        assert True
