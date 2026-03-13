"""Verify subpackage inherited parallelizable("children") from parent."""

import threading

from tests.pkg_parallel.sub._state import SubState


def test_sub_all_ran():
    """Barrier proves all 5 tests across 3 subpackage modules ran concurrently."""
    SubState.start.wait()
    SubState.log["verify_ran"] = threading.current_thread().name
    SubState.done.wait()
    assert {"a1", "a2", "b1"}.issubset(SubState.log.keys())


def test_sub_used_threads():
    """Verify subpackage tests ran on multiple threads."""
    SubState.start.wait()
    SubState.log["verify_threads"] = threading.current_thread().name
    SubState.done.wait()
    threads = set(SubState.log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"
