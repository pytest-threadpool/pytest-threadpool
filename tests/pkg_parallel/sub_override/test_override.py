"""Subpackage with own parallelizable("parameters") overrides parent's "children"."""

import threading

import pytest


class TestOverrideScope:
    """Parametrized variants run in parallel (parameters scope from sub_override),
    NOT cross-module children scope from grandparent."""

    param_log = {}

    @pytest.mark.parametrize("v", [0, 1, 2])
    def test_param(self, v):
        self.param_log[v] = threading.current_thread().name


def test_override_verify():
    """All 3 parametrized variants ran."""
    assert set(TestOverrideScope.param_log.keys()) == {0, 1, 2}


class TestOverrideBareSequential:
    """Without parametrize, 'parameters' scope has no effect --
    bare methods should run sequentially (no children parallelism)."""

    order = []

    def test_first(self):
        import time
        time.sleep(0.05)
        self.order.append("first")

    def test_second(self):
        self.order.append("second")

    def test_verify_order(self):
        assert self.order == ["first", "second"]
