"""Module A in the package-parallel sub-package."""

import threading

from tests.pkg_parallel import pkg_start, pkg_done, pkg_log, pkg_lock


class TestClassA:
    def test_a1(self):
        pkg_start.wait()
        with pkg_lock:
            pkg_log["a1"] = threading.current_thread().name
        pkg_done.wait()

    def test_a2(self):
        pkg_start.wait()
        with pkg_lock:
            pkg_log["a2"] = threading.current_thread().name
        pkg_done.wait()
