"""Parallel group with --maxfail: stops execution after N failures."""

import pytest


@pytest.mark.parallelizable("children")
class TestFirstGroup:
    def test_fail_a(self):
        pytest.fail("intentional failure a")

    def test_fail_b(self):
        pytest.fail("intentional failure b")

    def test_fail_c(self):
        pytest.fail("intentional failure c")


@pytest.mark.parallelizable("children")
class TestSecondGroup:
    def test_d(self):
        pass

    def test_e(self):
        pass
