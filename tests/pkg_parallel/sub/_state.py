"""Shared state for subpackage cross-module parallel tests."""

import threading


class SubState:
    """Barriers and log for proving inherited parallelism in subpackage.

    5 tests across 3 modules: test_sub_a(2) + test_sub_b(1) + test_sub_verify(2).
    """

    start = threading.Barrier(5, timeout=10)
    done = threading.Barrier(5, timeout=10)
    log = {}
