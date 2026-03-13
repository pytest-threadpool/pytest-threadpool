"""Module A in the package-parallel sub-package."""

import threading

from tests.pkg_parallel._state import PkgState


class TestClassA:
    def test_a1(self):
        PkgState.start.wait()
        PkgState.log["a1"] = threading.current_thread().name
        PkgState.done.wait()

    def test_a2(self):
        PkgState.start.wait()
        PkgState.log["a2"] = threading.current_thread().name
        PkgState.done.wait()
