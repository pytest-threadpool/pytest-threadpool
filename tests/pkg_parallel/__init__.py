import threading

import pytest

pytestmark = [pytest.mark.parallelizable("children"), pytest.mark.parallel_only]

# Shared barriers for all 6 tests across 3 modules in this package.
# _start proves concurrency, _done ensures writes complete before verify.
pkg_start = threading.Barrier(6, timeout=10)
pkg_done = threading.Barrier(6, timeout=10)
pkg_log = {}
pkg_lock = threading.Lock()
