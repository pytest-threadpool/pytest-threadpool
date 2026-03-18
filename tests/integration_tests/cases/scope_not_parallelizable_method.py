"""@not_parallelizable on a method opts it out of class children batch."""

import time
from typing import ClassVar

from pytest_threadpool import not_parallelizable, parallelizable


@parallelizable("children")
class TestMixed:
    log: ClassVar[list] = []

    def test_parallel_a(self):
        time.sleep(0.05)
        self.log.append("a")

    @not_parallelizable
    def test_seq_b(self):
        self.log.append("b")

    def test_parallel_c(self):
        self.log.append("c")


def test_verify():
    assert "a" in TestMixed.log
    assert "b" in TestMixed.log
    assert "c" in TestMixed.log
