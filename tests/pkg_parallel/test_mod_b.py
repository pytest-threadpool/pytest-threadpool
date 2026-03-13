"""Module B in the package-parallel sub-package."""

import threading

from tests.pkg_parallel._state import PkgState


def test_bare_b1():
    PkgState.start.wait()
    PkgState.log["b1"] = threading.current_thread().name
    PkgState.done.wait()


def test_bare_b2():
    PkgState.start.wait()
    PkgState.log["b2"] = threading.current_thread().name
    PkgState.done.wait()
