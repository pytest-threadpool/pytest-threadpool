"""Verify cross-module parallelism via package marker."""

import threading

import pytest

from tests.pkg_parallel._state import PkgState

pytestmark = pytest.mark.parallel_only


def test_cross_module_all_ran():
    """Barrier proves all 8 tests from 4 modules run concurrently."""
    PkgState.start.wait()
    PkgState.log["verify_ran"] = threading.current_thread().name
    PkgState.done.wait()
    assert {"a1", "a2", "b1", "b2", "d1", "d2"}.issubset(PkgState.log.keys())


def test_cross_module_used_threads():
    """Verify that tests from different modules ran on multiple threads."""
    PkgState.start.wait()
    PkgState.log["verify_threads"] = threading.current_thread().name
    PkgState.done.wait()
    threads = set(PkgState.log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"
