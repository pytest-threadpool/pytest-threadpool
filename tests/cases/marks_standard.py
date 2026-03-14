"""Case: standard pytest markers under parallel execution.

Verifies skip, skipif, xfail, and parametrize work correctly
inside a parallelizable class.
"""
import pytest


@pytest.mark.parallelizable("children")
class TestStandardMarks:
    @pytest.mark.skip(reason="intentional skip")
    def test_skipped(self):
        pass

    @pytest.mark.skipif(True, reason="condition is true")
    def test_skipif(self):
        pass

    @pytest.mark.xfail(reason="expected failure")
    def test_xfail(self):
        assert False

    @pytest.mark.parametrize("x", [1, 2, 3])
    def test_param(self, x):
        assert x > 0

    def test_plain(self):
        pass
