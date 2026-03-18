"""Case: tests with staggered sleep times to verify incremental reporting.

A conftest plugin writes report timestamps to a file. The fast tests
should be reported well before the slow test finishes.
"""

import time

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestStaggered:
    def test_fast_a(self):
        pass

    def test_fast_b(self):
        pass

    def test_fast_c(self):
        pass

    def test_slow(self):
        time.sleep(1)
