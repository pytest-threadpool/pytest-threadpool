"""Two parallel groups with a sequential test between them.

Used to verify newline separation between consecutive groups and
that stream proxy suppression applies to both groups independently.
"""

import time

import pytest

from pytest_threadpool import not_parallelizable, parallelizable


@parallelizable("children")
class TestGroupA:
    @pytest.mark.parametrize("n", range(3))
    def test_a(self, n):
        print(f"GROUP_A_OUTPUT_{n}")
        time.sleep(0.02)


@not_parallelizable
def test_sequential():
    print("SEQ_OUTPUT")


@parallelizable("children")
class TestGroupB:
    @pytest.mark.parametrize("n", range(3))
    def test_b(self, n):
        print(f"GROUP_B_OUTPUT_{n}")
        time.sleep(0.02)
