"""Fixture teardown exceptions must not skip remaining finalizers."""
import pytest


cleanup_log = []


@pytest.fixture
def resource_a():
    cleanup_log.append("setup_a")
    yield "a"
    cleanup_log.append("teardown_a")
    raise RuntimeError("teardown_a failed")


@pytest.fixture
def resource_b():
    cleanup_log.append("setup_b")
    yield "b"
    cleanup_log.append("teardown_b")


@pytest.mark.parallelizable("children")
class TestTeardownException:
    def test_uses_both(self, resource_a, resource_b):
        assert resource_a == "a"
        assert resource_b == "b"

    def test_standalone(self, resource_b):
        assert resource_b == "b"


def test_verify_all_teardowns_ran():
    """Both teardowns must have run despite resource_a's teardown raising."""
    assert "teardown_a" in cleanup_log, "failing finalizer must still execute"
    assert cleanup_log.count("teardown_b") == 2, "resource_b finalizer must run for both tests"
