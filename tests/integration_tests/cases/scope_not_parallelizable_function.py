"""@not_parallelizable on bare functions in a parallel module."""

import time

from pytest_threadpool import not_parallelizable, parallelizable

pytestmark = parallelizable("children")


@not_parallelizable
def test_seq_a():
    time.sleep(0.05)
    print("ORDER:a")


@not_parallelizable
def test_seq_b():
    print("ORDER:b")
