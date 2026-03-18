"""Parallel group where skip reduces items to one, triggering single-worker fallback."""

from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    log: ClassVar[list] = []


@parallelizable("children")
class TestSingleAfterSkip:
    @pytest.mark.skipif("True", reason="always skip")
    def test_skipped(self):
        pass

    def test_runs(self):
        TestState.log.append("ran")


def test_verify():
    assert TestState.log == ["ran"]
