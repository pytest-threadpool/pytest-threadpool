"""Module-level parallelizable("children"): all classes get parallel methods,
bare functions form their own parallel group."""

import threading

import pytest

pytestmark = [pytest.mark.parallelizable("children"), pytest.mark.parallel_only]


# ── bare functions parallelized via module marker ─────────────────────────
# All bare functions in this module form ONE parallel batch.
# Two-phase barrier: _start proves concurrency, _done ensures writes complete.

_func_start = threading.Barrier(4, timeout=10)
_func_done = threading.Barrier(4, timeout=10)
_func_log = {}
_func_lock = threading.Lock()


def test_mod_func_a():
    _func_start.wait()
    with _func_lock:
        _func_log["a"] = threading.current_thread().name
    _func_done.wait()


def test_mod_func_b():
    _func_start.wait()
    with _func_lock:
        _func_log["b"] = threading.current_thread().name
    _func_done.wait()


def test_mod_func_c():
    _func_start.wait()
    with _func_lock:
        _func_log["c"] = threading.current_thread().name
    _func_done.wait()


def test_mod_funcs_verify():
    """All 4 bare functions run in parallel; barriers prove concurrency."""
    _func_start.wait()
    _func_done.wait()
    assert set(_func_log.keys()) == {"a", "b", "c"}
    threads = set(_func_log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"


# ── class inherits module parallelizable("children") ─────────────────────

class TestModuleInheritedParallel:
    """Class without its own marker inherits module-level children."""

    barrier = threading.Barrier(3, timeout=10)
    log = {}
    lock = threading.Lock()

    def test_a(self):
        self.barrier.wait()
        with self.lock:
            self.log["a"] = threading.current_thread().name

    def test_b(self):
        self.barrier.wait()
        with self.lock:
            self.log["b"] = threading.current_thread().name

    def test_c(self):
        self.barrier.wait()
        with self.lock:
            self.log["c"] = threading.current_thread().name
