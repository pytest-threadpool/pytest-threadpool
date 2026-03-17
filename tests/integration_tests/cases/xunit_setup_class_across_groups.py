"""setup_class/teardown_class: once per class, independent across parallel groups."""

import threading
from typing import ClassVar

import pytest

lock = threading.Lock()


@pytest.mark.parallelizable("children")
class TestGroupA:
    setup_ids: ClassVar[list] = []

    @classmethod
    def setup_class(cls):
        with lock:
            cls.setup_ids.append(threading.current_thread().name)

    @classmethod
    def teardown_class(cls):
        with lock:
            cls.setup_ids.append("teardown_a")

    def test_a1(self):
        assert len([x for x in self.setup_ids if x != "teardown_a"]) == 1

    def test_a2(self):
        assert len([x for x in self.setup_ids if x != "teardown_a"]) == 1


@pytest.mark.parallelizable("children")
class TestGroupB:
    setup_ids: ClassVar[list] = []

    @classmethod
    def setup_class(cls):
        with lock:
            cls.setup_ids.append(threading.current_thread().name)

    @classmethod
    def teardown_class(cls):
        with lock:
            cls.setup_ids.append("teardown_b")

    def test_b1(self):
        assert len([x for x in self.setup_ids if x != "teardown_b"]) == 1

    def test_b2(self):
        assert len([x for x in self.setup_ids if x != "teardown_b"]) == 1


def test_verify():
    # Each class had exactly one setup_class call
    a_setups = [x for x in TestGroupA.setup_ids if x != "teardown_a"]
    b_setups = [x for x in TestGroupB.setup_ids if x != "teardown_b"]
    assert len(a_setups) == 1, f"setup_class ran {len(a_setups)} times for A"
    assert len(b_setups) == 1, f"setup_class ran {len(b_setups)} times for B"
    # Both teardowns ran
    assert "teardown_a" in TestGroupA.setup_ids
    assert "teardown_b" in TestGroupB.setup_ids
