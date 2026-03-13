"""Shared state for cross-module parallel tests in pkg_parallel."""

import threading


class PkgState:
    """Barriers and log shared across all modules in the package batch.

    start/done are two-phase barriers: start proves concurrency,
    done ensures writes complete before verification.
    """

    start = threading.Barrier(8, timeout=10)
    done = threading.Barrier(8, timeout=10)
    log = {}
