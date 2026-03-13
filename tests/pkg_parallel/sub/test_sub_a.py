"""Subpackage module A -- no markers, inherits from grandparent package."""

import threading

from tests.pkg_parallel.sub._state import SubState


def test_sub_a1():
    SubState.start.wait()
    SubState.log["a1"] = threading.current_thread().name
    SubState.done.wait()


def test_sub_a2():
    SubState.start.wait()
    SubState.log["a2"] = threading.current_thread().name
    SubState.done.wait()
