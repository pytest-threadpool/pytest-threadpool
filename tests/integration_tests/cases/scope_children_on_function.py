"""Case: @parallelizable('children') applied to a standalone function.

BUG-2: Should emit a warning and run sequentially, not silently ignore.
"""

import pytest


@pytest.mark.parallelizable("children")
def test_lone_function():
    pass


def test_normal():
    pass
