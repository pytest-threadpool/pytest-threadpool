"""Module-level parallelizable("children"): all classes get parallel methods,
bare functions form their own parallel group."""

import threading

import pytest

from tests.markers import parallelizable

pytestmark = [parallelizable("children"), pytest.mark.parallel_only]


# -- bare functions parallelized via module marker --
# All bare functions in this module form ONE parallel batch.
# Two-phase barrier: _start proves concurrency, _done ensures writes complete.

class _FuncState:
    start = threading.Barrier(4, timeout=10)
    done = threading.Barrier(4, timeout=10)
    log = {}


def test_mod_func_a():
    _FuncState.start.wait()
    _FuncState.log["a"] = threading.current_thread().name
    _FuncState.done.wait()


def test_mod_func_b():
    _FuncState.start.wait()
    _FuncState.log["b"] = threading.current_thread().name
    _FuncState.done.wait()


def test_mod_func_c():
    _FuncState.start.wait()
    _FuncState.log["c"] = threading.current_thread().name
    _FuncState.done.wait()


def test_mod_funcs_verify():
    """All 4 bare functions run in parallel; barriers prove concurrency."""
    _FuncState.start.wait()
    _FuncState.done.wait()
    assert set(_FuncState.log.keys()) == {"a", "b", "c"}
    threads = set(_FuncState.log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"


# -- class inherits module parallelizable("children") --

class TestModuleInheritedParallel:
    """Class without its own marker inherits module-level children."""

    barrier = threading.Barrier(3, timeout=10)
    log = {}

    def test_a(self):
        self.barrier.wait()
        self.log["a"] = threading.current_thread().name

    def test_b(self):
        self.barrier.wait()
        self.log["b"] = threading.current_thread().name

    def test_c(self):
        self.barrier.wait()
        self.log["c"] = threading.current_thread().name
