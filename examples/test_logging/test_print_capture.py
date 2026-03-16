"""print() in parallel tests — capture and suppression.

pytest's capture fixtures (``capsys``, ``capfd``) are NOT thread-safe:
they fail with "cannot use capsys and capsys at the same time" when
requested by parallel tests.

However, ``print()`` output from worker threads is **suppressed by
default** during parallel execution — pytest-threadpool installs
thread-local stream proxies that buffer worker output, preventing
interleaved lines in the test report.

**Behavior by mode:**

- **Default** (capture enabled): worker ``print()`` is silently
  suppressed — output does not appear in the terminal.
- **``-s``** (``--capture=no``): suppression is disabled — output
  from all threads interleaves freely (you asked for it).
- **Dynamic mode** (real terminal, non-verbose): the live progress
  line may also overwrite any leaked output.

**What to use instead for debug output:**

- ``tmp_path`` — write to a per-test file (see test_file_logging.py).
- ``logging`` with a per-test ``FileHandler`` (see test_log_capture.py).
- A shared thread-safe collection (see test_log_capture.py).
"""

from time import sleep

import pytest


class TestPrintInParallel:
    """Demonstrates print() behavior in parallel tests."""

    @pytest.mark.parametrize("_worker", range(4))
    def test_print_is_suppressed(self, _worker):
        """Worker print() is captured into a buffer and does not reach the terminal.

        Run with ``-s`` to disable suppression and see interleaved output.
        """
        print(f"worker {_worker}: starting")
        sleep(0.01)
        print(f"worker {_worker}: done")
