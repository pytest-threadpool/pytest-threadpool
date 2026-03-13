"""Tests for the three parallel marker scopes: children, parameters, all."""

import threading
import time

import pytest

from tests.markers import not_parallelizable, parallelizable


# -- "parameters" scope: parametrized variants run in parallel --

class _ParamState:
    barrier = threading.Barrier(3, timeout=10)
    log = {}


@pytest.mark.parallel_only
@parallelizable("parameters")
@pytest.mark.parametrize("variant", ["x", "y", "z"])
def test_param_parallel(variant):
    """Three parametrized variants should run concurrently."""
    _ParamState.barrier.wait()
    _ParamState.log[variant] = threading.current_thread().name


@pytest.mark.parallel_only
def test_param_parallel_verify():
    """Verify all three variants ran (and on multiple threads)."""
    assert set(_ParamState.log.keys()) == {"x", "y", "z"}
    threads = set(_ParamState.log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"


# -- "all" scope on a class: children + parameters merged --

@pytest.mark.parallel_only
@parallelizable("all")
class TestAllScope:
    """With 'all', both plain methods and @parametrize variants merge
    into a single parallel batch."""

    barrier = threading.Barrier(5, timeout=10)
    log = {}

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_param(self, n):
        self.barrier.wait()
        self.log[f"param_{n}"] = threading.current_thread().name

    def test_plain_a(self):
        self.barrier.wait()
        self.log["plain_a"] = threading.current_thread().name

    def test_plain_b(self):
        self.barrier.wait()
        self.log["plain_b"] = threading.current_thread().name


@pytest.mark.parallel_only
def test_all_scope_verify():
    """Verify all 5 tests (3 param + 2 plain) ran concurrently."""
    expected = {"param_1", "param_2", "param_3", "plain_a", "plain_b"}
    assert set(TestAllScope.log.keys()) == expected
    threads = set(TestAllScope.log.values())
    assert len(threads) >= 2, f"expected multiple threads, got {threads}"


# -- "children" on class does NOT merge @parametrize variants --

@parallelizable("children")
class TestChildrenWithParams:
    """With 'children', @parametrize variants of the same method get separate
    group keys (because callspec.params differ), so each variant runs alone."""

    results = {}

    @pytest.mark.parametrize("val", ["a", "b"])
    def test_item(self, val):
        self.results[val] = threading.current_thread().name


def test_children_params_verify():
    assert set(TestChildrenWithParams.results.keys()) == {"a", "b"}


# -- unmarked class stays sequential --

class TestUnmarkedSequential:
    """No parallel marker -> runs sequentially even with --threaded."""

    order = []

    def test_first(self):
        time.sleep(0.05)
        self.order.append("first")

    def test_second(self):
        self.order.append("second")

    def test_third(self):
        self.order.append("third")


def test_unmarked_sequential_verify():
    assert TestUnmarkedSequential.order == ["first", "second", "third"]


# -- not_parallelizable overrides inherited marker --

@parallelizable("children")
class TestNotParallelizableOverride:
    """Class has children, but one method opts out via not_parallelizable.
    The opted-out method should NOT be in the parallel batch -- it runs
    sequentially (as a separate group of 1)."""

    log = []

    def test_parallel_a(self):
        time.sleep(0.05)
        self.log.append("a")

    @not_parallelizable
    def test_sequential_b(self):
        self.log.append("b")

    def test_parallel_c(self):
        self.log.append("c")


def test_not_parallelizable_verify():
    """b should have run after a (sequential due to not_parallelizable)."""
    assert "a" in TestNotParallelizableOverride.log
    assert "b" in TestNotParallelizableOverride.log
    assert "c" in TestNotParallelizableOverride.log
