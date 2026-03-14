"""parallel_only marker skips tests when --freethreaded is not passed."""
import pytest


@pytest.mark.parallel_only
def test_needs_threads():
    pass


def test_normal():
    pass
