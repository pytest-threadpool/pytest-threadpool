"""Case: custom user-defined markers under parallel execution.

Verifies that custom markers work for filtering with -m expressions
inside a parallelizable class.
"""

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestCustomMarks:
    @pytest.mark.smoke
    def test_smoke_only(self):
        pass

    @pytest.mark.regression
    def test_regression_only(self):
        pass

    @pytest.mark.smoke
    @pytest.mark.regression
    def test_both(self):
        pass

    def test_unmarked(self):
        pass
