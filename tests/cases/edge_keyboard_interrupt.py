"""Test body raises KeyboardInterrupt during parallel execution."""

import pytest


@pytest.mark.parallelizable("children")
class TestKeyboardInterrupt:
    def test_normal(self):
        assert True

    def test_interrupts(self):
        raise KeyboardInterrupt

    def test_also_normal(self):
        assert True
