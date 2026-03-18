"""Function-scoped fixtures get fresh values per test."""

from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestFuncScope:
    call_log: ClassVar[list] = []

    @pytest.fixture(autouse=True)
    def counter(self):
        idx = len(self.call_log)
        self.call_log.append(f"setup_{idx}")
        return idx

    def test_a(self, counter):
        assert isinstance(counter, int)

    def test_b(self, counter):
        assert isinstance(counter, int)

    def test_c(self, counter):
        assert isinstance(counter, int)


def test_verify():
    setups = [x for x in TestFuncScope.call_log if x.startswith("setup_")]
    assert len(setups) == 3
