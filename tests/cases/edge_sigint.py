"""Slow parallel tests for SIGINT handling verification."""
import time
import pytest


teardown_ran = False


@pytest.fixture(scope="class")
def tracked_resource():
    yield "resource"
    global teardown_ran
    teardown_ran = True


@pytest.mark.parallelizable("children")
class TestSlowParallel:
    def test_slow_a(self, tracked_resource):
        time.sleep(30)

    def test_slow_b(self, tracked_resource):
        time.sleep(30)

    def test_slow_c(self, tracked_resource):
        time.sleep(30)
