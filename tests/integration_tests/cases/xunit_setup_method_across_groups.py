"""setup_method/teardown_method fire for every method across separate parallel classes."""

import threading

import pytest

lock = threading.Lock()
all_setups: list = []
all_teardowns: list = []


@pytest.mark.parallelizable("children")
class TestGroupA:
    barrier = threading.Barrier(2, timeout=10)

    def setup_method(self, method):
        with lock:
            all_setups.append(f"A.{method.__name__}")

    def teardown_method(self, method):
        with lock:
            all_teardowns.append(f"A.{method.__name__}")

    def test_a1(self):
        self.barrier.wait()

    def test_a2(self):
        self.barrier.wait()


@pytest.mark.parallelizable("children")
class TestGroupB:
    barrier = threading.Barrier(2, timeout=10)

    def setup_method(self, method):
        with lock:
            all_setups.append(f"B.{method.__name__}")

    def teardown_method(self, method):
        with lock:
            all_teardowns.append(f"B.{method.__name__}")

    def test_b1(self):
        self.barrier.wait()

    def test_b2(self):
        self.barrier.wait()


def test_verify():
    expected_setups = {"A.test_a1", "A.test_a2", "B.test_b1", "B.test_b2"}
    assert expected_setups == set(all_setups), f"setup_method: {all_setups}"
    assert expected_setups == set(all_teardowns), f"teardown_method: {all_teardowns}"
