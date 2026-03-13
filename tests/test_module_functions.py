"""Module-level bare functions -- always run sequentially per conftest logic."""

import threading
from time import sleep


class _State:
    execution_log = []


def test_bare_func_a():
    sleep(0.1)
    _State.execution_log.append(("a", threading.current_thread().name))


def test_bare_func_b():
    sleep(0.1)
    _State.execution_log.append(("b", threading.current_thread().name))


def test_bare_func_c():
    sleep(0.1)
    _State.execution_log.append(("c", threading.current_thread().name))


def test_bare_funcs_ran_sequentially():
    """Verify all bare functions executed (order preserved, main thread)."""
    names = [name for name, _ in _State.execution_log]
    assert names == ["a", "b", "c"]
    threads = {t for _, t in _State.execution_log}
    assert len(threads) == 1, f"bare functions should run on one thread, got {threads}"
