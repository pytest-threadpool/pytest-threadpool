"""Test that package-level children works on classes, unless overridden."""

import threading
import time

import pytest

from tests.markers import not_parallelizable, parallelizable
from tests.pkg_parallel._state import PkgState


class TestInheritsPackage:
    """No own marker -- inherits package children scope, joins cross-module batch."""

    def test_d1(self):
        PkgState.start.wait()
        PkgState.log["d1"] = threading.current_thread().name
        PkgState.done.wait()

    def test_d2(self):
        PkgState.start.wait()
        PkgState.log["d2"] = threading.current_thread().name
        PkgState.done.wait()


@parallelizable("parameters")
class TestNarrowerScope:
    """Own 'parameters' marker overrides package 'children'.

    Parametrized variants run in parallel with each other,
    but do NOT join the cross-module package batch.
    """

    param_log = {}

    @pytest.mark.parametrize("x", [0, 1, 2])
    def test_param(self, x):
        self.param_log[x] = threading.current_thread().name

    def test_param_used_threads(self):
        """Verify parametrized variants ran."""
        assert set(self.param_log.keys()) == {0, 1, 2}

    def test_not_in_pkg_batch(self):
        """The package barrier (exact party count) would deadlock if
        this class had joined, proving it stayed out."""
        assert "param_0" not in PkgState.log


@parallelizable("children")
class TestClassLevelChildren:
    """Own 'children' marker overrides package scope.

    Methods run in parallel within the class batch, but NOT as part
    of the cross-module package batch. The package barrier's exact
    party count would deadlock if these joined.
    """

    barrier = threading.Barrier(2, timeout=10)
    log = {}

    def test_own_a(self):
        self.barrier.wait()
        self.log["a"] = threading.current_thread().name

    def test_own_b(self):
        self.barrier.wait()
        self.log["b"] = threading.current_thread().name


@not_parallelizable
class TestNotParallelizable:
    """not_parallelizable overrides the package marker.

    Tests run sequentially despite the package having children scope.
    """

    order = []

    def test_seq_a(self):
        time.sleep(0.05)
        self.order.append("a")

    def test_seq_b(self):
        self.order.append("b")

    def test_seq_verify(self):
        assert self.order == ["a", "b"]
