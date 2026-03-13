"""Verify cross-module parallelism via package marker."""

import threading

import pytest

from tests.pkg_parallel import pkg_start, pkg_done, pkg_log, pkg_lock

pytestmark = pytest.mark.parallel_only


def test_cross_module_all_ran():
    """Barrier proves all 6 tests from 3 modules run concurrently."""
    pkg_start.wait()
    pkg_done.wait()
    assert {"a1", "a2", "b1", "b2"}.issubset(pkg_log.keys())


def test_cross_module_used_threads():
    """Verify that tests from different modules ran on multiple threads."""
    pkg_start.wait()
    with pkg_lock:
        pkg_log["verify"] = threading.current_thread().name
    pkg_done.wait()
    threads = set(pkg_log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"
