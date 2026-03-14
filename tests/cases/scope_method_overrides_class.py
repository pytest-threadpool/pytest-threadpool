"""Method's own 'parameters' overrides class 'children'."""
import threading

import pytest


@pytest.mark.parallelizable("children")
class TestOverride:
    child_barrier = threading.Barrier(2, timeout=10)

    def test_child_a(self):
        self.child_barrier.wait()

    def test_child_b(self):
        self.child_barrier.wait()

    @pytest.mark.parallelizable("parameters")
    @pytest.mark.parametrize("v", [1, 2, 3])
    def test_own_param(self, v):
        pass


def test_verify():
    # If own param joined children batch, barrier(2) would deadlock
    assert True
