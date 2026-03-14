"""Single-method class — falls back to sequential without error."""

import pytest


@pytest.mark.parallelizable("children")
class TestSolo:
    def test_only(self):
        assert True
