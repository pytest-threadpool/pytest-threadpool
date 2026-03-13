"""Module B in the package-parallel sub-package."""

import threading

from tests.pkg_parallel import pkg_start, pkg_done, pkg_log, pkg_lock


def test_bare_b1():
    pkg_start.wait()
    with pkg_lock:
        pkg_log["b1"] = threading.current_thread().name
    pkg_done.wait()


def test_bare_b2():
    pkg_start.wait()
    with pkg_lock:
        pkg_log["b2"] = threading.current_thread().name
    pkg_done.wait()
