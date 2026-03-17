"""setup_module/teardown_module: runs exactly once across multiple parallel groups."""

import threading
from typing import ClassVar

import pytest

lock = threading.Lock()


class State:
    setup_count: ClassVar[int] = 0
    teardown_count: ClassVar[int] = 0


def setup_module(module):
    with lock:
        State.setup_count += 1


def teardown_module(module):
    with lock:
        State.teardown_count += 1


@pytest.mark.parallelizable("children")
class TestGroupA:
    def test_a1(self):
        assert State.setup_count == 1

    def test_a2(self):
        assert State.setup_count == 1


@pytest.mark.not_parallelizable
def test_sequential_between():
    assert State.setup_count == 1
    assert State.teardown_count == 0


@pytest.mark.parallelizable("children")
class TestGroupB:
    def test_b1(self):
        assert State.setup_count == 1

    def test_b2(self):
        assert State.setup_count == 1
