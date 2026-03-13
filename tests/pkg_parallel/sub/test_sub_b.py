"""Subpackage module B -- proves cross-module parallelism inherited."""

import threading

from tests.pkg_parallel.sub._state import SubState


class TestSubClass:
    """Class in subpackage inherits package-level children."""

    def test_sub_b1(self):
        SubState.start.wait()
        SubState.log["b1"] = threading.current_thread().name
        SubState.done.wait()
