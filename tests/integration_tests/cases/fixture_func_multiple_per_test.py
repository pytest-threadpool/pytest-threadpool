"""Multiple function-scoped fixtures per test all get independent values."""

import threading
from typing import ClassVar

import pytest


class TestState:
    setup_counts: ClassVar[dict] = {"alpha": 0, "beta": 0, "gamma": 0}
    lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture
def alpha():
    with TestState.lock:
        TestState.setup_counts["alpha"] += 1
        idx = TestState.setup_counts["alpha"]
    return f"alpha_{idx}"


@pytest.fixture
def beta():
    with TestState.lock:
        TestState.setup_counts["beta"] += 1
        idx = TestState.setup_counts["beta"]
    return f"beta_{idx}"


@pytest.fixture
def gamma():
    with TestState.lock:
        TestState.setup_counts["gamma"] += 1
        idx = TestState.setup_counts["gamma"]
    return f"gamma_{idx}"


@pytest.mark.parallelizable("children")
class TestMultipleFixtures:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, alpha, beta, gamma):
        assert alpha.startswith("alpha_")
        assert beta.startswith("beta_")
        assert gamma.startswith("gamma_")
        self.barrier.wait()

    def test_b(self, alpha, beta, gamma):
        assert alpha.startswith("alpha_")
        assert beta.startswith("beta_")
        assert gamma.startswith("gamma_")
        self.barrier.wait()

    def test_c(self, alpha, beta, gamma):
        assert alpha.startswith("alpha_")
        assert beta.startswith("beta_")
        assert gamma.startswith("gamma_")
        self.barrier.wait()


def test_verify():
    # Each fixture was set up 3 times (once per test)
    assert TestState.setup_counts["alpha"] == 3
    assert TestState.setup_counts["beta"] == 3
    assert TestState.setup_counts["gamma"] == 3
