"""Bare module functions run sequentially on one thread."""

import threading
from time import sleep
from typing import ClassVar


class _State:
    execution_log: ClassVar[list] = []


def test_a():
    sleep(0.05)
    _State.execution_log.append(("a", threading.current_thread().name))


def test_b():
    _State.execution_log.append(("b", threading.current_thread().name))


def test_c():
    _State.execution_log.append(("c", threading.current_thread().name))


def test_verify():
    names = [name for name, _ in _State.execution_log]
    assert names == ["a", "b", "c"]
    threads = {t for _, t in _State.execution_log}
    assert len(threads) == 1
