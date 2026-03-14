"""@not_parallelizable on bare functions in a parallel module."""
import time

import pytest

pytestmark = pytest.mark.parallelizable("children")


@pytest.mark.not_parallelizable
def test_seq_a():
    time.sleep(0.05)
    print("ORDER:a")


@pytest.mark.not_parallelizable
def test_seq_b():
    print("ORDER:b")
